package com.uniapp.booking.domain;

import com.uniapp.booking.common.BizException;
import com.uniapp.booking.common.ErrorCode;
import com.uniapp.booking.config.BookingProperties;
import com.uniapp.booking.mq.BookingCreatedEvent;
import com.uniapp.booking.mq.BookingProducer;
import com.uniapp.booking.web.dto.BookingCreateResponse;
import com.uniapp.booking.web.dto.BookingRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeParseException;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/**
 * 预约写 + 我的预约（T-402 / T-501）。
 * 幂等语义按 R-02：命中返回首单 + duplicated=true，不报错；
 * Redis 只做前置短路，最终一致性由 DB `uk_contact_date_slot` 兜底。
 */
@Service
public class BookingService {

    private static final Logger log = LoggerFactory.getLogger(BookingService.class);
    private static final Set<String> SLOTS = Set.of("上午", "下午", "晚间");
    private static final String IDEM_PREFIX = "ub:idem:booking:"; // 架构 §5 Redis key 终表
    private static final int MAX_SIZE = 50;
    private static final int STATUS_PENDING = 0;

    private final BookingRepository repo;
    private final PackageRepository packages;
    private final StringRedisTemplate redis;
    private final BookingProducer producer;
    private final BookingProperties props;

    public BookingService(BookingRepository repo, PackageRepository packages, StringRedisTemplate redis,
                          BookingProducer producer, BookingProperties props) {
        this.repo = repo;
        this.packages = packages;
        this.redis = redis;
        this.producer = producer;
        this.props = props;
    }

    /**
     * 创建预约。
     *
     * @param userId 入参：JWT 解出的用户 id（不信任请求体/参数）
     * @param req    入参：套餐/日期/时段/联系人/备注
     * @return bookingId + status + duplicated（出参）
     * @throws BizException 40001 参数非法、40002 日期越界、40401 套餐不存在、50001 写入失败
     */
    public BookingCreateResponse create(long userId, BookingRequest req) {
        LocalDate bookDate = parseDate(req.bookDate());
        checkWindow(bookDate);
        String slot = req.slot().trim();
        if (!SLOTS.contains(slot)) {
            throw new BizException(ErrorCode.PARAM_INVALID, "slot 只能是 上午/下午/晚间");
        }
        PackageVO pkg = packages.findActiveById(req.packageId())
                .orElseThrow(() -> new BizException(ErrorCode.PACKAGE_NOT_FOUND));
        String contact = req.contact().trim();
        String key = idemKey(contact, bookDate, slot);

        Optional<BookingRow> duplicated = lookupByKey(key, contact, bookDate, slot, userId);
        if (duplicated.isPresent()) {
            return toDuplicated(duplicated.get());
        }

        long bookingId;
        try {
            bookingId = repo.insert(userId, pkg.id(), bookDate, slot, contact, trimToNull(req.remark()));
        } catch (DuplicateKeyException ex) {
            // 并发兜底（N4）：DB 唯一键胜出，删幂等键后返回首单（仅在首单属于当前用户时）
            dropKey(key);
            BookingRow first = repo.findByKey(contact, bookDate, slot)
                    .orElseThrow(() -> new BizException(ErrorCode.SERVICE_ERROR));
            ensureOwner(first, userId);
            return toDuplicated(first);
        }

        publishCreated(userId, bookingId, pkg.id(), bookDate, slot, contact);
        return new BookingCreateResponse(bookingId, STATUS_PENDING, false);
    }

    /**
     * 我的预约列表（按 JWT 用户过滤，时间倒序分页）。
     *
     * @param userId 入参：JWT 解出的用户 id
     * @param page   入参：页码（≤0 归一为 1）
     * @param size   入参：每页条数（1..50，越界归一为 10）
     * @return 当前页 + total（出参）
     */
    public BookingPage list(long userId, int page, int size) {
        int p = page <= 0 ? 1 : page;
        int s = size <= 0 || size > MAX_SIZE ? 10 : size;
        List<BookingItem> items = repo.findPageByUser(userId, (p - 1) * s, s)
                .stream().map(this::toItem).toList();
        return new BookingPage(items, repo.countByUser(userId), p, s);
    }

    /**
     * 幂等短路（N3）：Redis 命中 → 读同键行返回首单；未命中 → SETNX 占位。
     * Redis 不可用时降级为「不短路」，完全交给 DB 唯一键（可用性优先）。
     * 命中行必须属于当前用户（Q-011）：同手机号被别的账号占用时，不返回他人单。
     */
    private Optional<BookingRow> lookupByKey(String key, String contact, LocalDate bookDate, String slot, long userId) {
        try {
            String value = redis.opsForValue().get(key);
            if (value != null) {
                Optional<BookingRow> row = repo.findByKey(contact, bookDate, slot);
                if (row.isPresent()) {
                    ensureOwner(row.get(), userId);
                    return row;
                }
                redis.delete(key); // 键在行不在（数据被清理），清键后按新单处理
                return Optional.empty();
            }
            redis.opsForValue().setIfAbsent(key, "1",
                    Duration.ofSeconds(props.getIdem().getTtlSeconds()));
        } catch (BizException ex) {
            throw ex;
        } catch (Exception ex) {
            log.warn("幂等键读写失败，降级 DB 唯一键兜底: {}", ex.getMessage());
        }
        return Optional.empty();
    }

    /**
     * 同一手机号/日期/时段已被其他账号创建：不返回他人单（幂等语义只在同一账号内成立）。
     *
     * @param row    入参：唯一键命中的首单
     * @param userId 入参：当前登录用户
     * @throws BizException 40001 提示换手机号或时段
     */
    private void ensureOwner(BookingRow row, long userId) {
        if (row.userId() != userId) {
            throw new BizException(ErrorCode.PARAM_INVALID, "该手机号当天该时段已有预约，请更换手机号或时段");
        }
    }

    private void dropKey(String key) {
        try {
            redis.delete(key);
        } catch (Exception ex) {
            log.warn("幂等键删除失败（TTL 到期自动释放）: {}", ex.getMessage());
        }
    }

    /** 事件发布失败只记日志：预约已落库，不能因为通知链路把主流程打回。 */
    private void publishCreated(long userId, long bookingId, long packageId,
                                LocalDate bookDate, String slot, String contact) {
        try {
            producer.publishCreated(new BookingCreatedEvent("booking.created", bookingId, userId, packageId,
                    bookDate.toString(), slot, maskPhone(contact),
                    LocalDateTime.now().withNano(0).toString()));
        } catch (Exception ex) {
            log.error("预约 {} 已落库，但 booking.created 事件发布失败（该单不会进 notify_log）: {}",
                    bookingId, ex.getMessage());
        }
    }

    /** 幂等键 = ub:idem:booking:{sha256(phone|date|slot)[:32]}，key 里不落手机号明文。 */
    private String idemKey(String contact, LocalDate bookDate, String slot) {
        String raw = contact + "|" + bookDate + "|" + slot;
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(raw.getBytes(StandardCharsets.UTF_8));
            return IDEM_PREFIX + HexFormat.of().formatHex(digest).substring(0, 32);
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("JVM 不支持 SHA-256", ex);
        }
    }

    private LocalDate parseDate(String text) {
        try {
            return LocalDate.parse(text);
        } catch (DateTimeParseException ex) {
            throw new BizException(ErrorCode.PARAM_INVALID, "bookDate 格式需为 YYYY-MM-DD");
        }
    }

    /** 可预约窗口：今天 ~ 今天 + window-days（默认 30）；过去/超范围 → 40002。 */
    private void checkWindow(LocalDate bookDate) {
        LocalDate today = LocalDate.now();
        LocalDate last = today.plusDays(props.getWindowDays());
        if (bookDate.isBefore(today) || bookDate.isAfter(last)) {
            throw new BizException(ErrorCode.DATE_OUT_OF_RANGE,
                    "可预约范围为 " + today + " ~ " + last);
        }
    }

    private BookingCreateResponse toDuplicated(BookingRow row) {
        return new BookingCreateResponse(row.id(), row.status(), true);
    }

    private BookingItem toItem(BookingRow row) {
        return new BookingItem(row.id(), row.packageId(), row.packageTitle(),
                row.bookDate() == null ? null : row.bookDate().toString(), row.slot(),
                maskPhone(row.contact()), row.status(), statusText(row.status()),
                row.createdAt() == null ? null : row.createdAt().toString().replace('T', ' '));
    }

    private String statusText(int status) {
        return switch (status) {
            case 1 -> "已确认";
            case 2 -> "已取消";
            default -> "待确认";
        };
    }

    /** 138****0000：列表只回脱敏号，原始号留在 booking 表。 */
    private String maskPhone(String phone) {
        if (phone == null || phone.length() < 7) {
            return phone;
        }
        return phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
    }

    private String trimToNull(String text) {
        return StringUtils.hasText(text) ? text.trim() : null;
    }
}
