package com.uniapp.booking.mq;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.DirectExchange;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MQ 拓扑（T-403）：booking.exchange(direct) → booking.notify.queue →（重试 3 次后）booking.dlx → booking.notify.dlq。
 * 队列由生产者侧声明，消费者 @RabbitListener 只引用队列名，避免两边参数不一致导致 406。
 */
@Configuration
public class RabbitConfig {

    public static final String EXCHANGE = "booking.exchange";
    public static final String DLX = "booking.dlx";
    public static final String NOTIFY_QUEUE = "booking.notify.queue";
    public static final String DLQ = "booking.notify.dlq";
    public static final String ROUTING_KEY = "booking.created";
    public static final String DLQ_ROUTING_KEY = "booking.notify.dlq";

    /** 业务主交换机（direct，持久化）。 */
    @Bean
    public DirectExchange bookingExchange() {
        return new DirectExchange(EXCHANGE, true, false);
    }

    /** 死信交换机（direct，持久化）。 */
    @Bean
    public DirectExchange bookingDeadLetterExchange() {
        return new DirectExchange(DLX, true, false);
    }

    /** 通知队列：拒收（重试耗尽）后按死信路由转 DLQ。 */
    @Bean
    public Queue bookingNotifyQueue() {
        return QueueBuilder.durable(NOTIFY_QUEUE)
                .deadLetterExchange(DLX)
                .deadLetterRoutingKey(DLQ_ROUTING_KEY)
                .build();
    }

    /** 死信队列：留证 + 人工排查入口。 */
    @Bean
    public Queue bookingNotifyDlq() {
        return QueueBuilder.durable(DLQ).build();
    }

    @Bean
    public Binding bookingNotifyBinding() {
        return BindingBuilder.bind(bookingNotifyQueue()).to(bookingExchange()).with(ROUTING_KEY);
    }

    @Bean
    public Binding bookingDlqBinding() {
        return BindingBuilder.bind(bookingNotifyDlq()).to(bookingDeadLetterExchange()).with(DLQ_ROUTING_KEY);
    }

    /** JSON 消息体（record 可反序列化）；Boot 会自动把它接到 RabbitTemplate 与监听容器。 */
    @Bean
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }
}
