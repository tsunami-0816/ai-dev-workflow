package com.uniapp.booking.domain;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;

/**
 * package 表访问（D-11 / D-12）。只查上架（status=1），按 sort 升序。
 */
@Repository
public class PackageRepository {

    private static final String BASE_SQL =
            "SELECT id, title, price, cover_url, tags, summary, status FROM package WHERE status = 1 ";

    private final JdbcTemplate jdbc;

    public PackageRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 查询全部上架套餐（入参无；出参按 sort 升序的列表）。 */
    public List<PackageVO> findAllActive() {
        return jdbc.query(BASE_SQL + "ORDER BY sort ASC, id ASC", (rs, i) -> map(rs));
    }

    /** 按 id 查询上架套餐；出参 empty 表示不存在/已下架。 */
    public Optional<PackageVO> findActiveById(long id) {
        List<PackageVO> rows = jdbc.query(BASE_SQL + "AND id = ?", (rs, i) -> map(rs), id);
        return rows.stream().findFirst();
    }

    private PackageVO map(java.sql.ResultSet rs) throws java.sql.SQLException {
        String tags = rs.getString("tags");
        return new PackageVO(
                rs.getLong("id"),
                rs.getString("title"),
                rs.getBigDecimal("price"),
                rs.getString("cover_url"),
                tags == null || tags.isBlank() ? List.of() : Arrays.asList(tags.split(",")),
                rs.getString("summary"),
                rs.getInt("status"));
    }
}
