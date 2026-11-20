package com.uniapp.booking.web;

import com.uniapp.booking.common.Result;
import com.uniapp.booking.domain.BookingPage;
import com.uniapp.booking.domain.BookingService;
import com.uniapp.booking.infra.JwtAuthFilter;
import com.uniapp.booking.web.dto.BookingCreateResponse;
import com.uniapp.booking.web.dto.BookingRequest;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 预约写 + 我的预约（T-402 / T-501）。
 * 两个接口都被 JwtAuthFilter 保护；userId 只从 JWT 解出的 attribute 取，请求参数里的 userId 一律忽略。
 */
@RestController
@RequestMapping("/api/bookings")
@SecurityRequirement(name = "bearerAuth")
public class BookingController {

    private final BookingService bookingService;

    public BookingController(BookingService bookingService) {
        this.bookingService = bookingService;
    }

    /**
     * 创建预约。
     *
     * @param req    入参：{packageId,bookDate,slot,contact,remark}
     * @param userId 入参：JwtAuthFilter 写入的 userId（不接收客户端传值）
     * @return {bookingId,status,duplicated}；重复提交 duplicated=true
     */
    @PostMapping
    public Result<BookingCreateResponse> create(@Valid @RequestBody BookingRequest req,
                                                @RequestAttribute(JwtAuthFilter.ATTR_USER_ID) long userId) {
        return Result.ok(bookingService.create(userId, req));
    }

    /**
     * 我的预约列表（按当前登录用户过滤）。
     *
     * @param page   入参：页码，默认 1
     * @param size   入参：每页条数，默认 10
     * @param userId 入参：JwtAuthFilter 写入的 userId（伪造 query userId 无效）
     * @return {list,total,page,size}
     */
    @GetMapping
    public Result<BookingPage> list(@RequestParam(defaultValue = "1") int page,
                                    @RequestParam(defaultValue = "10") int size,
                                    @RequestAttribute(JwtAuthFilter.ATTR_USER_ID) long userId) {
        return Result.ok(bookingService.list(userId, page, size));
    }
}
