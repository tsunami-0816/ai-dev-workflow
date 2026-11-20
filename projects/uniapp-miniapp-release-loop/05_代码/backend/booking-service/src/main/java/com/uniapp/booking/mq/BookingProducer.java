package com.uniapp.booking.mq;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * 预约事件生产者（T-403）。开启 publisher confirm 后同步等待 broker 确认（3s），
 * 未确认即抛异常，由 BookingService 记日志（主流程不回滚）。
 */
@Component
public class BookingProducer {

    private static final Logger log = LoggerFactory.getLogger(BookingProducer.class);
    private static final long CONFIRM_TIMEOUT_SECONDS = 3;

    private final RabbitTemplate rabbitTemplate;

    public BookingProducer(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    /**
     * 发布 booking.created。
     *
     * @param event 入参：预约事件
     * @throws IllegalStateException broker 未确认（nack / 超时 / 连接失败）
     */
    public void publishCreated(BookingCreatedEvent event) {
        CorrelationData correlation = new CorrelationData(UUID.randomUUID().toString());
        rabbitTemplate.convertAndSend(RabbitConfig.EXCHANGE, RabbitConfig.ROUTING_KEY, event, correlation);
        try {
            CorrelationData.Confirm confirm = correlation.getFuture().get(CONFIRM_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            if (!confirm.isAck()) {
                throw new IllegalStateException("broker nack: " + confirm.getReason());
            }
            log.info("booking.created 已确认 bookingId={} msgId={}", event.bookingId(), correlation.getId());
        } catch (IllegalStateException ex) {
            throw ex;
        } catch (Exception ex) {
            throw new IllegalStateException("MQ confirm 等待失败: " + ex.getMessage(), ex);
        }
    }
}
