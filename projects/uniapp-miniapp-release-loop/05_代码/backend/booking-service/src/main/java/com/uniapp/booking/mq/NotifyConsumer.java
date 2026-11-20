package com.uniapp.booking.mq;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.uniapp.booking.domain.BookingRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

/**
 * 预约通知消费者（T-404）。落 `notify_log`（uk_booking_event 幂等），
 * 抛异常时由 spring retry 重试 3 次，耗尽后 reject → DLX → booking.notify.dlq。
 */
@Component
public class NotifyConsumer {

    private static final Logger log = LoggerFactory.getLogger(NotifyConsumer.class);

    private final BookingRepository repo;
    private final ObjectMapper objectMapper;

    public NotifyConsumer(BookingRepository repo, ObjectMapper objectMapper) {
        this.repo = repo;
        this.objectMapper = objectMapper;
    }

    /**
     * 消费 booking.created。
     *
     * @param event 入参：预约事件（JSON 反序列化）
     * @throws IllegalException 事件缺 bookingId（触发重试/DLQ，不吞消息）
     */
    @RabbitListener(queues = RabbitConfig.NOTIFY_QUEUE)
    public void onBookingCreated(BookingCreatedEvent event) {
        if (event == null || event.bookingId() <= 0) {
            throw new IllegalArgumentException("booking.created 事件缺少 bookingId");
        }
        String payload = toJson(event);
        int rows = repo.insertNotifyLog(event.bookingId(), event.event(), payload);
        if (rows == 0) {
            log.info("notify_log 重复投递已忽略 bookingId={} event={}", event.bookingId(), event.event());
        } else {
            log.info("notify_log 写入成功 bookingId={} event={}", event.bookingId(), event.event());
        }
    }

    private String toJson(BookingCreatedEvent event) {
        try {
            return objectMapper.writeValueAsString(event);
        } catch (Exception ex) {
            throw new IllegalStateException("事件序列化失败: " + ex.getMessage(), ex);
        }
    }
}
