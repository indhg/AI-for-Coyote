import type { Server, ServerWebSocket } from 'bun';

// 服务监听端口
const PORT = numberFromEnv('PORT', 9998);
// 业务心跳广播间隔
const HEARTBEAT_MS = numberFromEnv('HEARTBEAT_INTERVAL', 30_000);
// 原生 WebSocket ping 发送间隔
const WS_PING_MS = numberFromEnv('WS_PING_INTERVAL', 10_000);
// 连续未响应 pong 的最大次数
const MAX_MISSED_WS_PONGS = numberFromEnv('MAX_MISSED_WS_PONGS', 3);
// 控制方无被控端接入时的最长空闲时间
const IDLE_TIMEOUT_MS = numberFromEnv('IDLE_TIMEOUT', 5 * 60_000);
// WebSocket 接入路径
const PREFIX = prefixFromEnv('PREFIX', '/');
// 控制方断开时用于关闭被控方的关闭码
const CLOSE_CONTROLLER_DISCONNECTED = 4000;
// 找不到目标控制方时使用的关闭码
const CLOSE_CONTROLLER_NOT_FOUND = 4001;
// 控制方空闲超时时使用的关闭码
const CLOSE_IDLE_TIMEOUT = 4002;
// 当前启用的最低日志等级
const ACTIVE_LOG_LEVEL = logLevelFromEnv();
// clientId 使用的随机字节数
const CLIENT_ID_BYTES = 4;

interface WSData {
    tid?: string;
}

type JsonObject = Record<string, unknown>;
type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface MessageFrame {
    type: 'message';
    clientId?: string;
    data?: unknown;
}

class RelayServer {
    readonly port: number;
    // 控制方可管理多个被控方，反向映射用于处理被控方上报和断开
    private sockets = new Set<ServerWebSocket<WSData>>();
    private wsToClientId = new Map<ServerWebSocket<WSData>, string>();
    private controllersById = new Map<string, ServerWebSocket<WSData>>();
    private controlledClients = new Map<
        ServerWebSocket<WSData>,
        Map<string, ServerWebSocket<WSData>>
    >();
    private clientToController = new Map<
        ServerWebSocket<WSData>,
        ServerWebSocket<WSData>
    >();
    private idleTimers = new Map<ServerWebSocket<WSData>, Timer>();
    private missedWsPongs = new Map<ServerWebSocket<WSData>, number>();
    private heartbeatTimer?: Timer;
    private wsPingTimer?: Timer;

    constructor(port = PORT) {
        this.port = port;
    }

    startHeartbeat(): void {
        if (this.heartbeatTimer) return;
        this.heartbeatTimer = setInterval(
            () => this.broadcastHeartbeat(),
            HEARTBEAT_MS,
        );
    }

    startWsPing(): void {
        if (this.wsPingTimer) return;
        this.wsPingTimer = setInterval(() => this.pingConnections(), WS_PING_MS);
    }

    sendFrame(ws: ServerWebSocket<WSData>, payload: JsonObject): void {
        ws.send(JSON.stringify(payload));
    }

    clientIdOf(ws: ServerWebSocket<WSData>): string {
        return this.wsToClientId.get(ws) ?? '-';
    }

    describeData(data: unknown): string {
        if (!isJsonObject(data)) return '操作=- 请求=-';
        const op = typeof data.m === 'string' ? data.m : '-';
        const reqId = typeof data.reqId === 'string' ? data.reqId : '-';
        return `操作=${op} 请求=${reqId}`;
    }

    private broadcastHeartbeat(): void {
        const payload = JSON.stringify({ type: 'heartbeat' });
        for (const ws of this.sockets) {
            if (ws.readyState !== WebSocket.OPEN) continue;
            ws.send(payload);
        }
    }

    private pingConnections(): void {
        // 使用原生 ping/pong 清理长期无响应的连接
        for (const ws of this.sockets) {
            if (ws.readyState !== WebSocket.OPEN) continue;

            const missed = this.missedWsPongs.get(ws) ?? 0;
            if (missed >= MAX_MISSED_WS_PONGS) {
                log(
                    'warn',
                    `WS探活超时 连接=${this.clientIdOf(ws)} 未响应=${missed}`,
                );
                ws.terminate();
                continue;
            }

            this.missedWsPongs.set(ws, missed + 1);
            ws.ping();
        }
    }

    onOpen(ws: ServerWebSocket<WSData>): void {
        const clientId = this.createClientId();
        this.sendFrame(ws, { type: 'hello', clientId });

        this.sockets.add(ws);
        this.wsToClientId.set(ws, clientId);
        this.missedWsPongs.set(ws, 0);

        // 携带 tid 的连接是被控方，否则作为新的控制方
        if (ws.data.tid) {
            this.attachClient(ws, clientId, ws.data.tid);
        } else {
            this.attachController(ws, clientId);
        }
    }

    onMessage(
        ws: ServerWebSocket<WSData>,
        message: string | Buffer<ArrayBuffer>,
    ) {
        let parsed: unknown;
        try {
            parsed = JSON.parse(message.toString());
        } catch {
            log('warn', `WS JSON无效 连接=${this.clientIdOf(ws)}`);
            return;
        }
        if (this.handlePingMessage(ws, parsed)) return;
        if (!isMessageFrame(parsed)) {
            log(
                'debug',
                `WS忽略帧 连接=${this.clientIdOf(ws)} 类型=${describeFrameType(parsed)}`,
            );
            return;
        }
        const msg = parsed;

        const clientId = this.wsToClientId.get(ws);
        if (!clientId) return;

        // 控制方消息按 clientId 下发给指定被控方
        if (this.controllersById.has(clientId)) {
            if (typeof msg.clientId !== 'string') {
                log('warn', `WS目标缺失 控制方=${clientId}`);
                this.sendFrame(ws, {
                    type: 'error',
                    code: 'bad_request',
                    message: 'message.clientId is required',
                });
                return;
            }

            const tid = msg.clientId;
            const clientWs = this.controlledClients.get(ws)?.get(tid);
            if (clientWs?.readyState === WebSocket.OPEN) {
                this.sendFrame(clientWs, { type: 'message', data: msg.data });
                log(
                    'info',
                    `WS转发 控制方=${clientId} 被控方=${tid} ${this.describeData(msg.data)}`,
                );
            } else {
                log('warn', `WS被控方不存在 控制方=${clientId} 被控方=${tid}`);
                this.sendFrame(ws, {
                    type: 'error',
                    code: 'client_not_found',
                    clientId: tid,
                });
            }
            return;
        }

        // 被控方消息统一上报给所属控制方
        const controllerWs = this.clientToController.get(ws);
        if (controllerWs?.readyState === WebSocket.OPEN) {
            this.sendFrame(controllerWs, {
                type: 'message',
                clientId,
                data: msg.data,
            });
            log(
                'info',
                `WS上报 被控方=${clientId} 控制方=${this.clientIdOf(controllerWs)} ${this.describeData(msg.data)}`,
            );
        } else {
            log('warn', `WS控制方缺失 被控方=${clientId}`);
        }
    }

    onPong(ws: ServerWebSocket<WSData>): void {
        this.missedWsPongs.set(ws, 0);
    }

    onClose(ws: ServerWebSocket<WSData>, code: number, reason: string): void {
        this.sockets.delete(ws);
        this.missedWsPongs.delete(ws);
        const clientId = this.wsToClientId.get(ws);
        this.wsToClientId.delete(ws);

        if (!clientId) return;

        // 控制方断开时关闭其全部被控方，避免孤立连接
        if (this.controllersById.has(clientId)) {
            this.controllersById.delete(clientId);
            const clients = this.controlledClients.get(ws);
            this.controlledClients.delete(ws);
            this.cancelIdleTimer(ws);

            if (clients) {
                for (const [cId, cWs] of clients) {
                    this.clientToController.delete(cWs);
                    this.sendFrame(cWs, {
                        type: 'controller_disconnected',
                        clientId,
                    });
                    cWs.close(CLOSE_CONTROLLER_DISCONNECTED, 'controller_disconnected');
                    log('info', `踢出被控方 被控方=${cId} 控制方=${clientId}`);
                }
            }
            log(
                'info',
                `控制方断开 控制方=${clientId} 码=${code} 原因=${reason || '-'} 踢出=${clients?.size ?? 0}`,
            );
            return;
        }

        const controllerWs = this.clientToController.get(ws);
        if (controllerWs) {
            this.clientToController.delete(ws);
            const clients = this.controlledClients.get(controllerWs);
            clients?.delete(clientId);

            if (controllerWs.readyState === WebSocket.OPEN) {
                this.sendFrame(controllerWs, {
                    type: 'client_disconnected',
                    clientId,
                });
                if (!clients || clients.size === 0) this.startIdleTimer(controllerWs);
            }
            log(
                'info',
                `被控方断开 被控方=${clientId} 控制方=${this.clientIdOf(controllerWs)} 码=${code} 原因=${reason || '-'}`,
            );
        }
    }

    private handlePingMessage(
        ws: ServerWebSocket<WSData>,
        message: unknown,
    ): boolean {
        if (!isJsonObject(message)) return false;
        if (message.type === 'pong') return true;
        if (message.type !== 'ping') return false;

        this.sendFrame(ws, { type: 'pong', ts: Date.now() });
        return true;
    }

    private createClientId(): string {
        // 生成短 ID，并确保当前进程内不重复
        const bytes = new Uint8Array(CLIENT_ID_BYTES);
        let clientId: string;
        do {
            crypto.getRandomValues(bytes);
            clientId = Array.from(bytes, (byte) =>
                byte.toString(16).padStart(2, '0'),
            ).join('');
        } while ([...this.wsToClientId.values()].includes(clientId));
        return clientId;
    }

    private attachController(
        ws: ServerWebSocket<WSData>,
        clientId: string,
    ) {
        this.controllersById.set(clientId, ws);
        this.controlledClients.set(ws, new Map());
        this.startIdleTimer(ws);
        log('info', `控制方连接 控制方=${clientId}`);
    }

    private attachClient(
        ws: ServerWebSocket<WSData>,
        clientId: string,
        tid: string,
    ) {
        const controllerWs = this.controllersById.get(tid);
        if (!controllerWs || controllerWs.readyState !== WebSocket.OPEN) {
            this.sendFrame(ws, { type: 'error', code: 'controller_not_found' });
            ws.close(CLOSE_CONTROLLER_NOT_FOUND, 'controller_not_found');
            log(
                'warn',
                `被控方拒绝 被控方=${clientId} 目标=${tid} 原因=控制方不存在`,
            );
            return;
        }

        const clients = this.controlledClients.get(controllerWs);
        if (!clients) {
            this.sendFrame(ws, { type: 'error', code: 'controller_not_found' });
            ws.close(CLOSE_CONTROLLER_NOT_FOUND, 'controller_not_found');
            log(
                'error',
                `被控方拒绝 被控方=${clientId} 目标=${tid} 原因=控制方映射缺失`,
            );
            return;
        }

        clients.set(clientId, ws);
        this.clientToController.set(ws, controllerWs);
        this.cancelIdleTimer(controllerWs);

        this.sendFrame(ws, {
            type: 'controller_attached',
            clientId: tid,
        });
        this.sendFrame(controllerWs, { type: 'client_attached', clientId });
        log(
            'info',
            `被控方接入 被控方=${clientId} 控制方=${tid} 总数=${clients.size}`,
        );
    }

    private startIdleTimer(controllerWs: ServerWebSocket<WSData>) {
        // 没有被控方接入的控制方会在超时后自动关闭
        this.cancelIdleTimer(controllerWs);
        const clientId = this.wsToClientId.get(controllerWs);
        const timer = setTimeout(() => {
            this.idleTimers.delete(controllerWs);
            if (controllerWs.readyState === WebSocket.OPEN) {
                this.sendFrame(controllerWs, { type: 'idle_timeout' });
                controllerWs.close(CLOSE_IDLE_TIMEOUT, 'idle_timeout');
                log('warn', `控制方空闲超时 控制方=${clientId ?? '-'}`);
            }
        }, IDLE_TIMEOUT_MS);
        this.idleTimers.set(controllerWs, timer);
        log('debug', `空闲计时开始 控制方=${clientId ?? '-'}`);
    }

    private cancelIdleTimer(controllerWs: ServerWebSocket<WSData>) {
        const timer = this.idleTimers.get(controllerWs);
        if (timer) {
            clearTimeout(timer);
            this.idleTimers.delete(controllerWs);
            log('debug', `空闲计时取消 控制方=${this.clientIdOf(controllerWs)}`);
        }
    }

}

const isJsonObject = (value: unknown): value is JsonObject =>
    typeof value === 'object' && value !== null && !Array.isArray(value);

const isMessageFrame = (value: unknown): value is MessageFrame =>
    isJsonObject(value) && value.type === 'message';

const describeFrameType = (value: unknown): string => {
    if (!isJsonObject(value)) return '-';
    return typeof value.type === 'string' ? value.type : '-';
};

function numberFromEnv(name: string, fallback: number): number {
    const value = Number(Bun.env[name]);
    return Number.isFinite(value) && value > 0 ? value : fallback;
}

function prefixFromEnv(name: string, fallback: string): string {
    // 统一为无尾斜杠的绝对路径，根路径除外
    const value = Bun.env[name]?.trim();
    if (!value) return fallback;
    const prefixed = value.startsWith('/') ? value : `/${value}`;
    return prefixed.length > 1 ? prefixed.replace(/\/+$/, '') : prefixed;
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

    const line = `[V4] ${message}`;
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
    req: Request,
    server: Server<WSData>,
): Response | undefined => {
    const url = new URL(req.url);

    // 只允许在全局前缀上升级 WebSocket
    if (url.pathname !== PREFIX) {
        return new Response('Not Found', { status: 404 });
    }

    const tid =
        url.searchParams.get('targetId') ??
        url.searchParams.get('tid') ??
        undefined;
    if (server.upgrade(req, { data: { tid } })) {
        log(
            'debug',
            `WS升级 角色=${tid ? '被控方' : '控制方'} 目标=${tid ?? '-'}`,
        );
        return;
    }

    return new Response('WebSocket upgrade required', { status: 426 });
};

const relay = new RelayServer();

Bun.serve<WSData>({
    hostname: '::',
    port: relay.port,
    fetch: handleFetch,
    websocket: {
        data: {} as WSData,
        open: (ws) => relay.onOpen(ws),
        message: (ws, msg) => relay.onMessage(ws, msg),
        pong: (ws) => relay.onPong(ws),
        close: (ws, code, reason) => relay.onClose(ws, code, reason),
    },
});

relay.startHeartbeat();
relay.startWsPing();
log('info', `服务启动 端口=${relay.port} 路径=${PREFIX}`);
