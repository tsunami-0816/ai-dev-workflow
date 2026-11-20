package com.uniapp.booking.web;

import com.uniapp.booking.common.Result;
import com.uniapp.booking.domain.PackagePage;
import com.uniapp.booking.domain.PackageService;
import com.uniapp.booking.domain.PackageVO;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 套餐浏览（D-11 / D-12）。两个接口匿名可读，不要求 JWT。
 */
@RestController
@RequestMapping("/api/packages")
public class PackageController {

    private final PackageService packageService;

    public PackageController(PackageService packageService) {
        this.packageService = packageService;
    }

    /**
     * 套餐列表（分页）。
     *
     * @param page 入参：页码，默认 1
     * @param size 入参：每页条数，默认 10
     * @return {list,total,page,size}
     */
    @GetMapping
    public Result<PackagePage> list(@RequestParam(defaultValue = "1") int page,
                                    @RequestParam(defaultValue = "10") int size) {
        return Result.ok(packageService.list(page, size));
    }

    /**
     * 套餐详情（路径参数，用于验证路由与参数绑定）。
     *
     * @param id 入参：套餐 id
     * @return 套餐视图；不存在 40401
     */
    @GetMapping("/{id}")
    public Result<PackageVO> detail(@PathVariable long id) {
        return Result.ok(packageService.detail(id));
    }
}
