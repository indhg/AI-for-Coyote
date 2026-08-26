import type { Server, ServerWebSocket } from 'bun';

// 服务监听端口
const PORT = numberFromEnv('PORT', 9999);
// 服务端心跳发送间隔
const HEARTBEAT_MS = numberFromEnv('HEARTBEAT_INTERVAL', 60_000);
// 未配对连接的最长空闲时间
const IDLE_TIMEOUT_MS = numberFromEnv('IDLE_TIMEOUT', 5 * 60_000);
// 每秒发送的波形数据包数量
const DEFAULT_PUNISHMENT_TIME = numberFromEnv('DEFAULT_PUNISHMENT_TIME', 1);
// 波形默认持续时间，单位为秒
const DEFAULT_PUNISHMENT_DURATION = numberFromEnv(
    'DEFAULT_PUNISHMENT_DURATION',
    5,
);
// 替换旧波形前的短暂等待时间
const PULSE_REPLACE_DELAY_MS = 150;
// targetId 无效时使用的 WebSocket 关闭码
const CLOSE_INVALID_TARGET_ID = 4001;

type ClientId = string;
type MessageType = string | number;
type LogLevel = 'debug' | 'info' | 'warn' | 'error';
type ChannelLetter = 'A' | 'B';
type ChannelNumber = 1 | 2;

// 当前启用的最低日志等级
const ACTIVE_LOG_LEVEL = logLevelFromEnv();

interface WSData {
    // WebSocket 升级时解析出的连接信息
    clientId?: ClientId;
    targetId?: ClientId;
    hasTargetId?: boolean;
}

interface ClientEntry {
    ws: ServerWebSocket<WSData>;
    createdAt: Date;
    lastHeartbeat: Date;
    idleTimer?: Timer;
}

interface ProtocolMessage {
    type: MessageType;
    clientId: ClientId;
    targetId: ClientId;
    message: string;
    channel?: string | number;
    strength?: number;
    time?: number;
    [key: string]: unknown;
}

interface RouteResult {
    ok: boolean;
    code: string;
}

interface TimerTask {
    clientId: ClientId;
    targetId: ClientId;
    channel: ChannelLetter;
    messages: ProtocolMessage[];
    targetWs: ServerWebSocket<WSData>;
    sourceWs: ServerWebSocket<WSData>;
    remaining: number;
    nextIndex: number;
    timer?: Timer;
}

interface PulseSequence {
    messages: ProtocolMessage[];
    packetCount: number;
    totalFrames?: number;
    parsed: boolean;
}

interface ParsedPulseMessage {
    frames: string[];
}

class V3SocketServer {
    readonly port: number;

    // 双向映射用于快速查找配对端，web 代表控制端，app 代表被控端
    private connections = new Map<ClientId, ClientEntry>();
    private wsToClientId = new Map<ServerWebSocket<WSData>, ClientId>();
    private webToApp = new Map<ClientId, ClientId>();
    private appToWeb = new Map<ClientId, ClientId>();
    private pulseTimers = new Map<string, TimerTask>();
    private heartbeatTimer?: Timer;

    constructor(port = PORT) {
        this.port = port;
    }

    onOpen(ws: ServerWebSocket<WSData>): void {
        const clientId = crypto.randomUUID();
        const targetId = ws.data.targetId?.trim() ?? '';

        log('debug', targetId);

        if (ws.data.hasTargetId && !this.isAvailableTarget(targetId)) {
            log('warn', `拒绝连接：无效 targetId=${targetId}`);
            this.closeInvalidTarget(ws, clientId, targetId);
            return;
        }

        ws.data.clientId = clientId;

        this.connections.set(clientId, {
            ws,
            createdAt: new Date(),
            lastHeartbeat: new Date(),
        });
        this.wsToClientId.set(ws, clientId);
        this.startIdleTimer(clientId);

        this.send(ws, {
            type: 'bind',
            clientId,
            targetId: '',
            message: 'targetId',
        });

        // 携带 targetId 的连接作为 APP 端直接加入指定控制端
        if (ws.data.hasTargetId) {
            const result = this.pair(targetId, clientId);
            if (!result.ok) {
                log(
                    'warn',
                    `拒绝连接：targetId=${targetId} appId=${clientId} code=${result.code}`,
                );
                this.cancelIdleTimer(clientId);
                this.connections.delete(clientId);
                this.wsToClientId.delete(ws);
                this.closeInvalidTarget(ws, clientId, targetId);
                return;
            }

            const bindMessage = {
                type: 'bind',
                clientId: targetId,
                targetId: clientId,
                message: result.code,
            };
            this.sendToClient(targetId, bindMessage);
            this.send(ws, bindMessage);
        }

        log(
            'info',
            `新 WebSocket 连接：${clientId}${targetId ? `，目标：${targetId}` : ''}，当前连接数：${this.connections.size}`,
        );
    }

    onMessage(
        ws: ServerWebSocket<WSData>,
        rawMessage: string | Buffer<ArrayBuffer>,
    ): void {
        const message = rawMessage.toString();
        log('debug', `收到消息 [${this.clientIdOf(ws)}]: ${message}`);

        const parsed = this.parseProtocolMessage(message);
        if (!parsed.ok) {
            log(
                'warn',
                `消息格式错误 [${this.clientIdOf(ws)}]: code=${parsed.code}`,
            );
            this.sendError(ws, '', '', parsed.code);
            return;
        }

        const data = parsed.data;
        if (!this.validateSource(data, ws)) {
            log(
                'warn',
                `非法消息来源 [${this.clientIdOf(ws)}]: clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }

        // 按 V3 消息类型分流，未特殊处理的消息直接转发给配对端
        const routeType = numericType(data.type);
        if (data.type === 'bind') {
            this.handleBind(ws, data);
            return;
        }
        if (isAppReportMessage(data.message)) {
            this.forwardMessage(ws, data);
            return;
        }
        if (routeType === 1 || routeType === 2 || routeType === 3) {
            this.handleStrengthAdjust(ws, data, routeType);
            return;
        }
        if (routeType === 4) {
            this.handleCustomStrength(ws, data);
            return;
        }
        if (data.type === 'clientMsg') {
            this.handleClientMessage(ws, data);
            return;
        }
        if (data.type === 'heartbeat') {
            return;
        }
        this.forwardMessage(ws, data);
    }

    onClose(
        ws: ServerWebSocket<WSData>,
        code: number,
        reason: string,
    ): void {
        const clientId = this.wsToClientId.get(ws);
        if (!clientId) return;

        this.cancelIdleTimer(clientId);
        this.wsToClientId.delete(ws);
        this.connections.delete(clientId);

        const pairedId = this.pairedId(clientId);
        const webId = this.webIdFor(clientId);
        const appId = webId ? this.webToApp.get(webId) : undefined;
        if (webId) this.clearClientTimers(webId);
        this.unpair(clientId);

        // 任一端断开时通知并关闭另一端，避免保留失效配对
        if (pairedId) {
            log('info', `[${clientId}] 断开，关联配对：${pairedId}`);
            const pairedClient = this.connections.get(pairedId);
            if (pairedClient?.ws.readyState === WebSocket.OPEN) {
                this.send(pairedClient.ws, {
                    type: 'break',
                    clientId: webId ?? pairedId,
                    targetId: appId ?? clientId,
                    message: '209',
                });
                pairedClient.ws.close(1000, 'partner_disconnected');
                log('debug', `已通知并关闭配对连接：${pairedId}`);
            }
        }

        log(
            'info',
            `[断开] ${clientId}，code=${code}，reason=${reason || '-'}，剩余连接数：${this.connections.size}`,
        );
    }

    startHeartbeat(): void {
        if (this.heartbeatTimer) return;
        this.heartbeatTimer = setInterval(() => {
            log(
                'debug',
                `发送心跳，当前连接数：${this.connections.size}, 配对数：${this.webToApp.size}`,
            );
            for (const [clientId, client] of this.connections) {
                if (client.ws.readyState !== WebSocket.OPEN) continue;
                client.lastHeartbeat = new Date();
                this.send(client.ws, {
                    type: 'heartbeat',
                    clientId,
                    targetId: this.pairedId(clientId) ?? '',
                    message: '200',
                });
            }
        }, HEARTBEAT_MS);
        log('info', `心跳启动 interval=${HEARTBEAT_MS}ms`);
    }

    private startIdleTimer(clientId: ClientId): void {
        // 只限制未配对连接，配对成功后会取消计时
        this.cancelIdleTimer(clientId);
        const client = this.connections.get(clientId);
        if (!client) return;

        client.idleTimer = setTimeout(() => {
            this.closeIfUnpaired(clientId);
        }, IDLE_TIMEOUT_MS);
        log('debug', `未配对超时计时开始：${clientId} timeout=${IDLE_TIMEOUT_MS}ms`);
    }

    private cancelIdleTimer(clientId: ClientId): void {
        const client = this.connections.get(clientId);
        if (!client?.idleTimer) return;

        clearTimeout(client.idleTimer);
        client.idleTimer = undefined;
    }

    private closeIfUnpaired(clientId: ClientId): void {
        const client = this.connections.get(clientId);
        if (!client || client.ws.readyState !== WebSocket.OPEN) return;
        if (this.isBound(clientId)) return;

        this.send(client.ws, {
            type: 'error',
            clientId,
            targetId: '',
            message: 'idle_timeout',
        });
        client.ws.close(1000, 'idle_timeout');
        log('warn', `未配对连接超时关闭：${clientId}`);
    }

    json(status: number, payload: unknown): Response {
        return new Response(JSON.stringify(payload), {
            status,
            headers: {
                'content-type': 'application/json; charset=utf-8',
                'access-control-allow-origin': '*',
            },
        });
    }

    private parseProtocolMessage(
        rawMessage: string | Buffer<ArrayBuffer>,
    ):
        | { ok: true; data: ProtocolMessage }
        | { ok: false; code: string } {
        // 先校验公共字段，具体业务字段由各处理器继续校验
        let parsed: unknown;
        try {
            parsed = JSON.parse(rawMessage.toString());
        } catch {
            return { ok: false, code: '403' };
        }

        if (!isPlainObject(parsed)) {
            return { ok: false, code: '403' };
        }
        if (!hasOwn(parsed, 'type') || !hasOwn(parsed, 'clientId')) {
            return { ok: false, code: '403' };
        }
        if (!hasOwn(parsed, 'targetId') || !hasOwn(parsed, 'message')) {
            return { ok: false, code: '403' };
        }
        if (
            !isProtocolType(parsed.type) ||
            typeof parsed.clientId !== 'string' ||
            typeof parsed.targetId !== 'string' ||
            typeof parsed.message !== 'string'
        ) {
            return { ok: false, code: '403' };
        }
        if (parsed.clientId.length === 0 || parsed.targetId.length === 0) {
            return { ok: false, code: '403' };
        }

        return { ok: true, data: parsed as ProtocolMessage };
    }

    private validateSource(
        data: ProtocolMessage,
        ws: ServerWebSocket<WSData>,
    ): boolean {
        const senderId = this.wsToClientId.get(ws);
        return senderId === data.clientId || senderId === data.targetId;
    }

    private handleBind(
        ws: ServerWebSocket<WSData>,
        data: ProtocolMessage,
    ): void {
        const { clientId: webId, targetId: appId } = data;
        const result = this.pair(webId, appId);
        log(
            'debug',
            `绑定请求 [${this.clientIdOf(ws)}]: web=${webId} app=${appId} code=${result.code}`,
        );
        const response = {
            type: 'bind',
            clientId: webId,
            targetId: appId,
            message: result.code,
        };

        if (!result.ok) {
            log('warn', `绑定失败：${webId} ↔ ${appId}，code=${result.code}`);
            this.send(ws, response);
            return;
        }

        this.sendToClient(webId, response);
        if (appId !== webId) this.sendToClient(appId, response);
    }

    private handleStrengthAdjust(
        ws: ServerWebSocket<WSData>,
        data: ProtocolMessage,
        routeType: 1 | 2 | 3,
    ): void {
        if (!this.isWebSender(ws, data)) {
            log(
                'warn',
                `强度调整来源非法：sender=${this.clientIdOf(ws)} clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }
        if (!this.isPaired(data.clientId, data.targetId)) {
            log(
                'warn',
                `强度调整配对无效：clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '402');
            return;
        }

        const channel = normalizeChannel(data.channel, 1);
        if (!channel) {
            log(
                'warn',
                `强度调整通道无效：clientId=${data.clientId} channel=${String(data.channel)}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '406');
            return;
        }

        // V3 APP 使用 0/1/2 表示减小、增大和指定强度
        const sendType = routeType - 1;
        const strength =
            routeType === 3 ? normalizeNumber(data.strength, 0) : 1;
        const strengthMessage = `strength-${channel.number}+${sendType}+${strength}`;
        const sent = this.sendToClient(data.targetId, {
            type: 'msg',
            clientId: data.clientId,
            targetId: data.targetId,
            message: strengthMessage,
        });

        if (!sent) {
            log('warn', `强度调整目标不存在：targetId=${data.targetId}`);
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }

        log('debug', `强度调整：${strengthMessage}`);
    }

    private handleCustomStrength(
        ws: ServerWebSocket<WSData>,
        data: ProtocolMessage,
    ): void {
        if (!this.isWebSender(ws, data)) {
            log(
                'warn',
                `指定强度来源非法：sender=${this.clientIdOf(ws)} clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }
        if (!this.isPaired(data.clientId, data.targetId)) {
            log(
                'warn',
                `指定强度配对无效：clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '402');
            return;
        }

        const channel = normalizeChannel(data.channel, 1);
        if (!channel) {
            log(
                'warn',
                `指定强度通道无效：clientId=${data.clientId} channel=${String(data.channel)}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '406');
            return;
        }

        if (data.message.includes('clear')) {
            const clearMessage = `clear-${channel.number}`;
            const sent = this.sendToClient(data.targetId, {
                type: 'msg',
                clientId: data.clientId,
                targetId: data.targetId,
                message: clearMessage,
            });
            if (!sent) {
                log('warn', `清除通道目标不存在：targetId=${data.targetId}`);
                this.sendError(ws, data.clientId, data.targetId, '404');
                return;
            }

            this.clearTimer(data.clientId, channel.letter);
            this.notifyDone(ws, data.clientId, data.targetId);
            log('debug', `清除通道：${clearMessage}`);
            return;
        }

        const strength = normalizeNumber(data.strength, 0);
        const strengthMessage = `strength-${channel.number}+2+${strength}`;
        const sent = this.sendToClient(data.targetId, {
            type: 'msg',
            clientId: data.clientId,
            targetId: data.targetId,
            message: strengthMessage,
        });
        if (!sent) {
            log('warn', `指定强度目标不存在：targetId=${data.targetId}`);
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }
        log('debug', `指定强度：${strengthMessage}`);
    }

    private handleClientMessage(
        ws: ServerWebSocket<WSData>,
        data: ProtocolMessage,
    ): void {
        if (!this.isWebSender(ws, data)) {
            log(
                'warn',
                `波形消息来源非法：sender=${this.clientIdOf(ws)} clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }
        if (!this.isPaired(data.clientId, data.targetId)) {
            log(
                'warn',
                `波形消息配对无效：clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '402');
            return;
        }

        const channel = normalizeChannel(data.channel);
        if (!channel) {
            log(
                'warn',
                `波形消息缺少通道：clientId=${data.clientId} targetId=${data.targetId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '406');
            return;
        }

        const target = this.connections.get(data.targetId);
        if (!target || target.ws.readyState !== WebSocket.OPEN) {
            log('warn', `波形消息目标不存在：targetId=${data.targetId}`);
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }

        // 将完整波形拆成固定频率的数据包后交给定时队列发送
        const time = normalizePositiveInteger(
            data.time,
            DEFAULT_PUNISHMENT_DURATION,
        );
        const sendsPerSecond = normalizeSendsPerSecond(
            DEFAULT_PUNISHMENT_TIME,
        );
        const intervalMs = 1000 / sendsPerSecond;
        const sequence = buildPulseSequence(
            data,
            channel.letter,
            time,
            sendsPerSecond,
        );

        this.queuePulse(
            data.clientId,
            data.targetId,
            channel,
            target.ws,
            sequence.messages,
            intervalMs,
            ws,
        );
        log(
            'info',
            `[${data.clientId}] 波形消息已发送：通道${channel.letter}, 包数${sequence.packetCount}, 时长${time}s${
                sequence.parsed && sequence.totalFrames
                    ? `, 总帧数${sequence.totalFrames}`
                    : ', 原始格式透传'
            }`,
        );
    }

    private forwardMessage(
        ws: ServerWebSocket<WSData>,
        data: ProtocolMessage,
    ): void {
        if (!this.isPaired(data.clientId, data.targetId)) {
            log(
                'warn',
                `转发消息配对无效：clientId=${data.clientId} targetId=${data.targetId} type=${String(data.type)}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '402');
            return;
        }

        const senderId = this.wsToClientId.get(ws);
        const recipientId =
            senderId === data.clientId ? data.targetId : data.clientId;
        const shouldSwapIds =
            data.type === 'msg' &&
            senderId !== undefined &&
            this.appToWeb.has(senderId);
        const sent = this.sendToClient(recipientId, {
            type: data.type,
            clientId: shouldSwapIds ? senderId : data.clientId,
            targetId: shouldSwapIds ? recipientId : data.targetId,
            message: data.message,
        });

        if (!sent) {
            log(
                'warn',
                `转发消息目标不存在：sender=${senderId ?? '-'} recipient=${recipientId}`,
            );
            this.sendError(ws, data.clientId, data.targetId, '404');
            return;
        }

        const messageKind = data.message.startsWith('feedback')
            ? 'feedback'
            : data.message.startsWith('strength')
              ? 'strength'
              : '普通消息';
        log(
            'debug',
            `转发${messageKind}：sender=${senderId ?? '-'} recipient=${recipientId} type=${String(data.type)} message=${data.message}`,
        );
    }

    private queuePulse(
        clientId: ClientId,
        targetId: ClientId,
        channel: { letter: ChannelLetter; number: ChannelNumber },
        targetWs: ServerWebSocket<WSData>,
        messages: ProtocolMessage[],
        intervalMs: number,
        sourceWs: ServerWebSocket<WSData>,
    ): void {
        const key = timerKey(clientId, channel.letter);
        const oldTask = this.pulseTimers.get(key);
        if (oldTask) {
            log('info', `[${key}] 清除现有定时器，准备发送新消息`);
            this.clearTimer(clientId, channel.letter);
            this.send(targetWs, {
                type: 'msg',
                clientId,
                targetId,
                message: `clear-${channel.number}`,
            });
            this.send(sourceWs, {
                type: 'notify',
                clientId,
                targetId,
                message: `当前通道${channel.letter}有正在发送的消息，覆盖之前的消息`,
            });

            setTimeout(() => {
                this.startPulse(
                    clientId,
                    targetId,
                    channel.letter,
                    targetWs,
                    messages,
                    intervalMs,
                    sourceWs,
                );
            }, PULSE_REPLACE_DELAY_MS);
            return;
        }

        this.startPulse(
            clientId,
            targetId,
            channel.letter,
            targetWs,
            messages,
            intervalMs,
            sourceWs,
        );
    }

    private startPulse(
        clientId: ClientId,
        targetId: ClientId,
        channel: ChannelLetter,
        targetWs: ServerWebSocket<WSData>,
        messages: ProtocolMessage[],
        intervalMs: number,
        sourceWs: ServerWebSocket<WSData>,
    ): void {
        const key = timerKey(clientId, channel);
        const firstMessage = messages[0];
        if (!firstMessage) {
            log('warn', `[${key}] 波形消息为空，停止发送`);
            this.notifyDone(sourceWs, clientId, targetId);
            return;
        }

        const task: TimerTask = {
            clientId,
            targetId,
            channel,
            messages,
            targetWs,
            sourceWs,
            remaining: messages.length,
            nextIndex: 0,
        };

        this.sendPulsePacket(task, firstMessage);
        task.remaining -= 1;
        task.nextIndex += 1;
        log('info', `[${key}] 消息发送中，剩余次数：${task.remaining}`);

        if (task.remaining <= 0) {
            log('info', `[${key}] 消息已发送完成（仅 1 条）`);
            this.notifyDone(sourceWs, clientId, targetId);
            return;
        }

        task.timer = setInterval(() => {
            if (targetWs.readyState !== WebSocket.OPEN) {
                log('warn', `[${key}] 目标连接已断开，停止发送`);
                this.clearTimer(clientId, channel);
                return;
            }

            const message = task.messages[task.nextIndex];
            if (!message) {
                log('warn', `[${key}] 波形消息序列已耗尽，停止发送`);
                this.clearTimer(clientId, channel);
                this.notifyDone(sourceWs, clientId, targetId);
                return;
            }

            this.sendPulsePacket(task, message);
            task.remaining -= 1;
            task.nextIndex += 1;
            if (task.remaining <= 0) {
                log('info', `[${key}] 消息发送完毕`);
                this.clearTimer(clientId, channel);
                this.notifyDone(sourceWs, clientId, targetId);
            }
        }, intervalMs);

        this.pulseTimers.set(key, task);
    }

    private sendPulsePacket(task: TimerTask, message: ProtocolMessage): void {
        const key = timerKey(task.clientId, task.channel);
        const packetIndex = task.nextIndex + 1;
        const packetCount = task.messages.length;
        const body = JSON.stringify(message);
        if (this.send(task.targetWs, message)) {
            log(
                'info',
                `[${key}] 实际发出包体 ${packetIndex}/${packetCount}: ${body}`,
            );
        }
    }

    private clearTimer(clientId: ClientId, channel: ChannelLetter): void {
        const key = timerKey(clientId, channel);
        const task = this.pulseTimers.get(key);
        if (!task) return;

        if (task.timer) clearInterval(task.timer);
        this.pulseTimers.delete(key);
        log('debug', `[${key}] 定时器已清除`);
    }

    private clearClientTimers(clientId: ClientId): void {
        let cleared = 0;
        for (const [key, task] of this.pulseTimers) {
            if (task.clientId !== clientId) continue;
            if (task.timer) clearInterval(task.timer);
            this.pulseTimers.delete(key);
            cleared += 1;
        }
        log('info', `[${clientId}] 清除了 ${cleared} 个定时器`);
    }

    private notifyDone(
        ws: ServerWebSocket<WSData>,
        clientId: ClientId,
        targetId: ClientId,
    ): void {
        this.send(ws, {
            type: 'notify',
            clientId,
            targetId,
            message: '发送完毕',
        });
    }

    private pair(webId: ClientId, appId: ClientId): RouteResult {
        if (webId === appId) return { ok: false, code: '401' };
        if (!this.connections.has(webId) || !this.connections.has(appId)) {
            return { ok: false, code: '401' };
        }
        if (this.isPaired(webId, appId)) {
            log('debug', `配对已存在，兼容重复绑定：${webId} ↔ ${appId}`);
            return { ok: true, code: '200' };
        }
        if (this.isBound(webId) || this.isBound(appId)) {
            return { ok: false, code: '400' };
        }

        // 同时保存正向和反向关系，保证两端都能常数时间查询
        this.webToApp.set(webId, appId);
        this.appToWeb.set(appId, webId);
        this.cancelIdleTimer(webId);
        this.cancelIdleTimer(appId);
        log('info', `配对成功：${webId} ↔ ${appId}`);
        return { ok: true, code: '200' };
    }

    private unpair(clientId: ClientId): void {
        const appId = this.webToApp.get(clientId);
        if (appId) {
            this.webToApp.delete(clientId);
            this.appToWeb.delete(appId);
            log('info', `解除配对：${clientId} ↔ ${appId}`);
            return;
        }

        const webId = this.appToWeb.get(clientId);
        if (webId) {
            this.appToWeb.delete(clientId);
            this.webToApp.delete(webId);
            log('info', `解除配对：${webId} ↔ ${clientId}`);
        }
    }

    private isBound(clientId: ClientId): boolean {
        return this.webToApp.has(clientId) || this.appToWeb.has(clientId);
    }

    private isAvailableTarget(clientId: ClientId): boolean {
        const client = this.connections.get(clientId);
        return (
            !!client &&
            client.ws.readyState === WebSocket.OPEN &&
            !this.isBound(clientId)
        );
    }

    private isPaired(clientId: ClientId, targetId: ClientId): boolean {
        return (
            this.webToApp.get(clientId) === targetId ||
            this.appToWeb.get(clientId) === targetId
        );
    }

    private pairedId(clientId: ClientId): ClientId | undefined {
        return this.webToApp.get(clientId) ?? this.appToWeb.get(clientId);
    }

    private webIdFor(clientId: ClientId): ClientId | undefined {
        if (this.webToApp.has(clientId)) return clientId;
        return this.appToWeb.get(clientId);
    }

    private isWebSender(
        ws: ServerWebSocket<WSData>,
        data: ProtocolMessage,
    ): boolean {
        return this.wsToClientId.get(ws) === data.clientId;
    }

    private clientIdOf(ws: ServerWebSocket<WSData>): ClientId {
        return this.wsToClientId.get(ws) ?? '-';
    }

    private sendToClient(clientId: ClientId, payload: ProtocolMessage): boolean {
        const client = this.connections.get(clientId);
        if (!client || client.ws.readyState !== WebSocket.OPEN) return false;
        return this.send(client.ws, payload);
    }

    private sendError(
        ws: ServerWebSocket<WSData>,
        clientId: ClientId,
        targetId: ClientId,
        code: string,
    ): void {
        log(
            'debug',
            `发送错误响应：clientId=${clientId || '-'} targetId=${targetId || '-'} code=${code}`,
        );
        this.send(ws, {
            type: 'error',
            clientId,
            targetId,
            message: code,
        });
    }

    private closeInvalidTarget(
        ws: ServerWebSocket<WSData>,
        clientId: ClientId,
        targetId: ClientId,
    ): void {
        this.sendError(ws, clientId, targetId, String(CLOSE_INVALID_TARGET_ID));
        ws.close(CLOSE_INVALID_TARGET_ID, 'invalid_target_id');
    }

    private send(
        ws: ServerWebSocket<WSData>,
        payload: {
            type: MessageType;
            clientId?: string;
            targetId?: string;
            message?: string;
        },
    ): boolean {
        if (ws.readyState !== WebSocket.OPEN) return false;
        try {
            ws.send(JSON.stringify(payload));
            return true;
        } catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            log('error', `发送消息失败：${message}`);
            return false;
        }
    }
}

const normalizeChannel = (
    value: unknown,
    fallback?: ChannelNumber,
): { letter: ChannelLetter; number: ChannelNumber } | undefined => {
    // 兼容协议中的数字通道和字母通道
    const normalized = value ?? fallback;
    if (normalized === 1 || normalized === '1' || normalized === 'A') {
        return { letter: 'A', number: 1 };
    }
    if (normalized === 2 || normalized === '2' || normalized === 'B') {
        return { letter: 'B', number: 2 };
    }
    if (normalized === 'a') return { letter: 'A', number: 1 };
    if (normalized === 'b') return { letter: 'B', number: 2 };
};

const buildPulseSequence = (
    data: ProtocolMessage,
    channel: ChannelLetter,
    time: number,
    sendsPerSecond: number,
): PulseSequence => {
    const packetCount = Math.max(1, time * sendsPerSecond);
    const baseMessage = {
        type: 'msg',
        clientId: data.clientId,
        targetId: data.targetId,
    };
    const parsed = parsePulseMessage(data.message);

    if (!parsed) {
        return {
            messages: Array.from({ length: packetCount }, () => ({
                ...baseMessage,
                message: `pulse-${data.message}`,
            })),
            packetCount,
            parsed: false,
        };
    }

    const totalFrames = Math.max(1, time * 10);
    const fittedFrames = fitFramesToLength(parsed.frames, totalFrames);
    const chunks = splitFrames(fittedFrames, packetCount);
    const messages = chunks.map((frames) => ({
        ...baseMessage,
        message: `pulse-${channel}:${JSON.stringify(frames)}`,
    }));

    return {
        messages,
        packetCount: messages.length,
        totalFrames,
        parsed: true,
    };
};

const parsePulseMessage = (message: string): ParsedPulseMessage | undefined => {
    const separatorIndex = message.indexOf(':');
    if (separatorIndex <= 0) return;

    let parsed: unknown;
    try {
        parsed = JSON.parse(message.slice(separatorIndex + 1));
    } catch {
        return;
    }

    if (
        !Array.isArray(parsed) ||
        parsed.length === 0 ||
        !parsed.every(
            (item) =>
                typeof item === 'string' && /^[0-9a-fA-F]{16}$/.test(item),
        )
    ) {
        return;
    }

    return {
        frames: parsed.map((item) => item.toUpperCase()),
    };
};

const fitFramesToLength = (frames: string[], totalFrames: number): string[] => {
    const firstFrame = frames[0];
    if (firstFrame === undefined) return [];

    return Array.from(
        { length: totalFrames },
        (_, index) => frames[index % frames.length] ?? firstFrame,
    );
};

const splitFrames = (frames: string[], packetCount: number): string[][] =>
    Array.from({ length: packetCount }, (_, index) => {
        const start = Math.floor((index * frames.length) / packetCount);
        const end = Math.floor(((index + 1) * frames.length) / packetCount);
        return frames.slice(start, end);
    }).filter((chunk) => chunk.length > 0);

const normalizeSendsPerSecond = (value: number): number => {
    const normalized = Math.trunc(value);
    if (!Number.isFinite(normalized) || normalized < 1) return 1;
    return Math.min(normalized, 10);
};

const normalizeNumber = (value: unknown, fallback: number): number => {
    const parsed = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(parsed)) return fallback;
    return Math.trunc(parsed);
};

const normalizePositiveInteger = (value: unknown, fallback: number): number => {
    const parsed = normalizeNumber(value, fallback);
    return parsed > 0 ? parsed : fallback;
};

const numericType = (type: MessageType): number | undefined => {
    if (typeof type === 'number') return type;
    if (/^\d+$/.test(type)) return Number(type);
};

const isAppReportMessage = (message: string): boolean =>
    message.startsWith('feedback') || message.startsWith('strength');

const timerKey = (clientId: ClientId, channel: ChannelLetter): string =>
    `${clientId}:${channel}`;

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const hasOwn = (value: object, key: string): boolean =>
    Object.prototype.hasOwnProperty.call(value, key);

const isProtocolType = (value: unknown): value is MessageType =>
    (typeof value === 'string' && value.length > 0) ||
    typeof value === 'number';

function numberFromEnv(name: string, fallback: number): number {
    const value = Number(Bun.env[name]);
    return Number.isFinite(value) && value > 0 ? value : fallback;
}

function logLevelFromEnv(): LogLevel {
    if (Bun.env.VERBOSE === 'true') return 'debug';

    const level = Bun.env.LOG_LEVEL?.toLowerCase();
    if (
        level === 'debug' ||
        level === 'info' ||
        level === 'warn' ||
        level === 'error'
    ) {
        return level;
    }

    return 'info';
}

// 日志等级越高，输出优先级越高
const LOG_WEIGHT: Record<LogLevel, number> = {
    debug: 10,
    info: 20,
    warn: 30,
    error: 40,
};

const log = (level: LogLevel, message: string): void => {
    if (LOG_WEIGHT[level] < LOG_WEIGHT[ACTIVE_LOG_LEVEL]) return;

    const timestamp = new Date().toISOString();
    const line = `${timestamp} [${level.toUpperCase()}] [V3] ${message}`;
    if (level === 'debug') {
        console.debug(line);
        return;
    }
    if (level === 'warn') {
        console.warn(line);
        return;
    }
    if (level === 'error') {
        console.error(line);
        return;
    }
    console.log(line);
};

const handleFetch = (
    relay: V3SocketServer,
    req: Request,
    server: Server<WSData>,
): Response | undefined => {
    // V3 通过路径末段传递目标 ID，其余 HTTP 请求仅返回升级提示
    const url = new URL(req.url);
    const rawTargetId =
        url.searchParams.get('targetId') || url.searchParams.get('tid') || url.pathname.slice(1).trim() || null;
    const data: WSData =
        rawTargetId === null
            ? {}
            : { targetId: rawTargetId.trim(), hasTargetId: true };

    if (server.upgrade(req, { data })) return;
    return relay.json(426, {
        ok: false,
        error: 'websocket_required',
        protocol: 'DG-LAB WebSocket V3',
    });
};

const relay = new V3SocketServer();

Bun.serve<WSData>({
    hostname: '::',
    port: relay.port,
    fetch: (req, server) => handleFetch(relay, req, server),
    websocket: {
        open: (ws) => relay.onOpen(ws),
        message: (ws, message) => relay.onMessage(ws, message),
        close: (ws, code, reason) => relay.onClose(ws, code, reason),
    },
});

relay.startHeartbeat();
log('info', `服务启动 port=${relay.port}`);
