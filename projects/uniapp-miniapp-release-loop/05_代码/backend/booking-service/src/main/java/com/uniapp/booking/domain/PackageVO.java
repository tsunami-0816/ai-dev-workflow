package com.uniapp.booking.domain;

import java.math.BigDecimal;
import java.util.List;

/**
 * 套餐对外视图（D-11 / D-12）：tags 由 DB 的逗号串拆分为数组。
 */
public record PackageVO(
        long id,
        String title,
        BigDecimal price,
        String coverUrl,
        List<String> tags,
        String summary,
        int status) {
}
