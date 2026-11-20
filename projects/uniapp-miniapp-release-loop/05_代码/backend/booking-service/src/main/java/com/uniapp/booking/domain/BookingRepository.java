package com.uniapp.booking.domain;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.Date;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

/**
 * booking / notify_log 表访问（T-402 / T-404 / T-501）。全部参数化 SQL，不拼字符串。
 */
@Repository
public class BookingRepository {

    private static final String ROW_SQL =
            "SELECT b.id, b.user_id, b.package_id, p.title AS package_title, b.book_date, b.slot, "
                    + "b.contact, b.remark, b.status, b.created_at "
                    + "FROM booking b LEFT JOIN package p ON p.id = b.package_id ";

    private final JdbcTemplate jdbc;

    public BookingRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * 写入一笔预约（靠 `uk_contact_date_slot` 唯一键兜底并发）。
     *
     * @param userId    入参：下单用户 id
     * @param packageId 入参：套餐 id
     * @param bookDate  入参：预约日期
     * @param slot      入参：时段
     * @param contact   入参：联系人手机号（幂等键组成）
     * @param remark    入参：备注（可 null）
     * @return 新预约主键（出参）
     * @throws org.springframework.dao.DuplicateKeyException 同人同日同时段已存在（1062）
     */
    public long insert(long userId, long packageId, LocalDate bookDate, String slot,
                       String contact, String remark) {
        KeyHolder kh = new GeneratedKeyHolder();
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO booking(user_id, package_id, book_date, slot, contact, remark) "
                            + "VALUES(?, ?, ?, ?, ?, ?)",
                    Statement.RETURN_GENERATED_KEYS);
            ps.setLong(1, userId);
            ps.setLong(2, packageId);
            ps.setDate(3, Date.valueOf(bookDate));
            ps.setString(4, slot);
            ps.setString(5, contact);
            ps.setString(6, remark);
            return ps;
        }, kh);
        Number key = kh.getKey();
        if (key == null) {
            throw new IllegalStateException("预约写入未返回主键");
        }
        return key.longValue();
    }

    /** 按唯一键（手机号 + 日期 + 时段）查首单；出参 empty 表示不存在。 */
    public Optional<BookingRow> findByKey(String contact, LocalDate bookDate, String slot) {
        List<BookingRow> rows = jdbc.query(
                ROW_SQL + "WHERE b.contact = ? AND b.book_date = ? AND b.slot = ?",
                this::mapRow, contact, Date.valueOf(bookDate), slot);
        return rows.stream().findFirst();
    }

    /**
     * 按用户分页查「我的预约」（时间倒序）。
     *
     * @param userId 入参：JWT 解出的用户 id
     * @param offset 入参：偏移量
     * @param limit  入参：每页条数
     * @return 当前页行（出参）
     */
    public List<BookingRow> findPageByUser(long userId, int offset, int limit) {
        return jdbc.query(ROW_SQL + "WHERE b.user_id = ? ORDER BY b.created_at DESC, b.id DESC LIMIT ? OFFSET ?",
                this::mapRow, userId, limit, offset);
    }

    /** 某用户预约总数（出参用于分页 total）。 */
    public long countByUser(long userId) {
        Long total = jdbc.queryForObject("SELECT COUNT(*) FROM booking WHERE user_id = ?", Long.class, userId);
        return total == null ? 0L : total;
    }

    /**
     * 消费者幂等落库：`uk_booking_event` 唯一键 + INSERT IGNORE。
     *
     * @param bookingId 入参：预约单号
     * @param event     入参：事件名（booking.created）
     * @param payload   入参：事件 JSON（≤1024 字符）
     * @return 实际写入行数；0 = 重复投递已忽略（出参）
     */
    public int insertNotifyLog(long bookingId, String event, String payload) {
        return jdbc.update("INSERT IGNORE INTO notify_log(booking_id, event, payload) VALUES(?, ?, ?)",
                bookingId, event, payload);
    }

    private BookingRow mapRow(ResultSet rs, int i) throws SQLException {
        return new BookingRow(
                rs.getLong("id"),
                rs.getLong("user_id"),
                rs.getLong("package_id"),
                rs.getString("package_title"),
                rs.getObject("book_date", LocalDate.class),
                rs.getString("slot"),
                rs.getString("contact"),
                rs.getString("remark"),
                rs.getInt("status"),
                rs.getObject("created_at", java.time.LocalDateTime.class));
    }
}
