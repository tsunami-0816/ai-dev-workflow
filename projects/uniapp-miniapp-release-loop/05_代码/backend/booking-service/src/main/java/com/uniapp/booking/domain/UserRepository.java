package com.uniapp.booking.domain;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.List;
import java.util.Optional;

/**
 * user 表访问（D-08 支撑）。只做参数化 SQL，不拼字符串。
 */
@Repository
public class UserRepository {

    private final JdbcTemplate jdbc;

    public UserRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 按 H5 账号查用户；出参 empty 表示不存在。 */
    public Optional<UserRow> findByAccount(String account) {
        List<UserRow> rows = jdbc.query(
                "SELECT id, account, password_hash, openid, nickname FROM user WHERE account = ?",
                (rs, i) -> new UserRow(rs.getLong("id"), rs.getString("account"),
                        rs.getString("password_hash"), rs.getString("openid"), rs.getString("nickname")),
                account);
        return rows.stream().findFirst();
    }

    /** 按小程序 openid 查用户；出参 empty 表示首次进入。 */
    public Optional<UserRow> findByOpenid(String openid) {
        List<UserRow> rows = jdbc.query(
                "SELECT id, account, password_hash, openid, nickname FROM user WHERE openid = ?",
                (rs, i) -> new UserRow(rs.getLong("id"), rs.getString("account"),
                        rs.getString("password_hash"), rs.getString("openid"), rs.getString("nickname")),
                openid);
        return rows.stream().findFirst();
    }

    /**
     * 首次 openid 登录建号。
     *
     * @param openid   入参：微信 openid（唯一）
     * @param nickname 入参：昵称，可空
     * @return 新用户主键（出参）
     */
    public long insertOpenidUser(String openid, String nickname) {
        KeyHolder kh = new GeneratedKeyHolder();
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO user(openid, nickname) VALUES(?, ?)", Statement.RETURN_GENERATED_KEYS);
            ps.setString(1, openid);
            ps.setString(2, nickname);
            return ps;
        }, kh);
        Number key = kh.getKey();
        if (key == null) {
            throw new IllegalStateException("openid 建号未返回主键");
        }
        return key.longValue();
    }

    /** 用户行快照（不直接暴露给 web 层）。 */
    public static class UserRow {
        private final long id;
        private final String account;
        private final String passwordHash;
        private final String openid;
        private final String nickname;

        public UserRow(long id, String account, String passwordHash, String openid, String nickname) {
            this.id = id;
            this.account = account;
            this.passwordHash = passwordHash;
            this.openid = openid;
            this.nickname = nickname;
        }

        public long getId() {
            return id;
        }

        public String getAccount() {
            return account;
        }

        public String getPasswordHash() {
            return passwordHash;
        }

        public String getOpenid() {
            return openid;
        }

        public String getNickname() {
            return nickname;
        }
    }
}
