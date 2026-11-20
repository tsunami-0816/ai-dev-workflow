package com.uniapp.booking.domain;

import java.util.List;

/**
 * 套餐分页出参（D-11）：page/size 不参与缓存 key，只在内存切片。
 */
public record PackagePage(List<PackageVO> list, long total, int page, int size) {
}
