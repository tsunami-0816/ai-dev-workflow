package com.uniapp.booking.domain;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uniapp.booking.common.BizException;
import com.uniapp.booking.common.ErrorCode;
import com.uniapp.booking.config.BookingProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.List;

/**
 * 套餐浏览（D-11 / D-12 / R-03）：单 key 缓存整表 + 内存分页。
 * Redis 不可用时降级直查 DB（可用性优先，架构 §7 异常分支）。
 */
@Service
public class PackageService {

    private static final Logger log = LoggerFactory.getLogger(PackageService.class);
    private static final String LIST_KEY = "ub:pkg:list";
    private static final int MAX_SIZE = 50;

    private final PackageRepository repo;
    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final BookingProperties props;

    public PackageService(PackageRepository repo, StringRedisTemplate redis,
                          ObjectMapper objectMapper, BookingProperties props) {
        this.repo = repo;
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.props = props;
    }

    /**
     * 列表分页。
     *
     * @param page 入参：页码（≤0 归一为 1）
     * @param size 入参：每页条数（1..50，越界归一为 10）
     * @return list/total/page/size（出参）
     */
    public PackagePage list(int page, int size) {
        int p = page <= 0 ? 1 : page;
        int s = size <= 0 || size > MAX_SIZE ? 10 : size;
        List<PackageVO> all = loadAll();
        int from = Math.min((p - 1) * s, all.size());
        int to = Math.min(from + s, all.size());
        return new PackagePage(all.subList(from, to), all.size(), p, s);
    }

    /**
     * 详情（与列表共用同一份缓存）。
     *
     * @param id 入参：套餐 id
     * @return 套餐视图（出参）
     * @throws BizException 40401 套餐不存在/已下架
     */
    public PackageVO detail(long id) {
        return loadAll().stream().filter(p -> p.id() == id).findFirst()
                .orElseThrow(() -> new BizException(ErrorCode.PACKAGE_NOT_FOUND));
    }

    /** 缓存回源单飞锁（Q-012）：同一实例内并发 miss 只回源一次 */
    private final Object loadLock = new Object();

    /** 缓存命中直接返回；miss 回源 DB 并写缓存。 */
    private List<PackageVO> loadAll() {
        try {
            List<PackageVO> cached = readCache();
            if (cached != null) {
                return cached;
            }
        } catch (Exception ex) {
            log.warn("套餐缓存读取失败，降级直查 DB: {}", ex.getMessage());
            return repo.findAllActive();
        }

        // 单飞：拿到锁后二次确认缓存，避免 N 个并发 miss 各打一次 DB
        synchronized (loadLock) {
            try {
                List<PackageVO> cached = readCache();
                if (cached != null) {
                    return cached;
                }
            } catch (Exception ex) {
                log.warn("套餐缓存二次读取失败，降级直查 DB: {}", ex.getMessage());
                return repo.findAllActive();
            }
            List<PackageVO> fresh = repo.findAllActive();
            writeCache(fresh);
            return fresh;
        }
    }

    /** 读缓存：命中返回列表，未命中返回 null；Redis/反序列化异常向上抛由调用方降级。 */
    private List<PackageVO> readCache() throws Exception {
        String json = redis.opsForValue().get(LIST_KEY);
        if (json == null || json.isBlank()) {
            return null;
        }
        return objectMapper.readValue(json, new TypeReference<List<PackageVO>>() {
        });
    }

    private void writeCache(List<PackageVO> rows) {
        try {
            redis.opsForValue().set(LIST_KEY, objectMapper.writeValueAsString(rows),
                    Duration.ofSeconds(props.getCache().getPackageTtlSeconds()));
        } catch (Exception ex) {
            log.warn("套餐缓存写入失败（不影响本次返回）: {}", ex.getMessage());
        }
    }
}
