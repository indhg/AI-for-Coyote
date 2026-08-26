# DG-LAB WebSocket Server

DG-LAB WebSocket Server 是 [DGLAB KIT](https://github.com/dungeonlab-open/dglab-kit/) 的服务端实现，基于 Bun 提供 DG-LAB APP 与控制端之间的 WebSocket Relay 服务。

它可以作为本地开发服务，也可以作为第三方业务服务与 DG-LAB APP 通信时的中转层。

当前包含两套协议服务：

| 服务 | 默认端口 | 说明 |
| --- | --- | --- |
| `v4-server.ts` | `9998` | DG-LAB 4 APP WebSocket Relay 服务，支持 `1 控制方 : N 被控方` |
| `v3-server.ts` | `9999` | 旧版 WebSocket 配对服务，支持 `1 控制方 : 1 被控方` |

## 快速开始

### 启动 V4 服务

```bash
bun run v4
```

默认监听：

```text
ws://127.0.0.1:9998
```

配合 `dglab-kit` 连接：

```ts
import { DglabSocket } from 'dglab-kit';

const socket = new DglabSocket({ url: 'ws://127.0.0.1:9998' });
const { targetId } = await socket.connect();

console.log('被控方配对 ID:', targetId);
```

被控方可通过携带 `tid` 的 URL 接入指定控制方：

```text
ws://127.0.0.1:9998?tid=控制方clientId
```

也可以拼接 DG-LAB 4 APP 控制二维码：

```ts
const qrcode = `https://dungeon-lab.cn/s/?v=1&action=socket&url=${encodeURIComponent('ws://127.0.0.1:9998?tid=' + targetId)}`;
```

### 启动 V3 服务

```bash
bun run v3
```

默认监听：

```text
ws://127.0.0.1:9999
```

配合 `dglab-kit` 连接：

```ts
import {
  DGLAB_SOCKET_VERSION,
  DglabSocket,
  V3Channel,
} from 'dglab-kit';

const socket = new DglabSocket({
  version: DGLAB_SOCKET_VERSION.V3,
  url: 'ws://127.0.0.1:9999',
});

const { targetId } = await socket.connect();
console.log('将控制方 ID 交给被控端:', targetId);

socket.on('client-attached', () => {
  socket.setStrength(V3Channel.A, 20);
});
```

### 开发模式

```bash
bun run dev:v4
bun run dev:v3
```

## 环境变量

可以复制 `.env.example` 为 `.env` 后按需修改。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | V4: `9998` / V3: `9999` | 服务监听端口 |
| `HEARTBEAT_INTERVAL` | V4: `30000` / V3: `60000` | 心跳发送间隔，单位 ms |
| `IDLE_TIMEOUT` | `300000` | V3 未配对连接 / V4 控制方无被控端接入时的空闲断开时间，单位 ms |
| `PREFIX` | `/` | V4 WebSocket 全局路径前缀，例如 `/v4` 或 `/relay/v4` |
| `DEFAULT_PUNISHMENT_TIME` | `1` | V3 波形消息每秒发送次数 |
| `DEFAULT_PUNISHMENT_DURATION` | `5` | V3 波形消息默认持续时间，单位秒 |
| `LOG_LEVEL` | `info` | 日志等级，支持 `debug`、`info`、`warn`、`error` |
| `VERBOSE` | `false` | 设置为 `true` 时强制开启 debug 日志 |

## V4 协议

V4 是推荐协议。控制方先连接服务端获取 `clientId`，被控方再通过 `tid=控制方clientId` 接入。控制方通过 WebSocket 向指定被控方发送消息。

```text
第三方控制端 <-> WebSocket Server <-> N 个 DG-LAB APP 终端
```

### V4 消息流程

V4 服务把连接分为控制方和被控方：

```text
1. 控制方连接 ws://host:9998
2. 服务端返回 hello，包含控制方 clientId
3. 被控方通过 ws://host:9998?tid=控制方clientId 接入
4. 服务端通知控制方 client_attached
5. 控制方通过 WebSocket 向指定被控方发送 message
6. 被控方处理后，可通过 message 上报数据
```

V4 的 `data` 是业务数据透传层。服务端只关心外层的 `type`、`clientId` 和 `data`，不会解析 DG-LAB 设备指令。实际设备控制指令建议由 `dglab-kit` 生成。

### V4 二维码

DG-LAB 4 APP 的 Socket 控制 V4 二维码可以由控制方 `targetId` 拼接生成：

```ts
const wsUrl = `wss://your-domain.example/v4?tid=${targetId}`;
const qrcode = `https://dungeon-lab.cn/s/?v=1&action=socket&url=${encodeURIComponent(wsUrl)}`;
```

本地开发可以使用 `ws://127.0.0.1:9998?tid=...` 测试；配置 `PREFIX=/v4` 后应使用 `ws://127.0.0.1:9998/v4?tid=...`。公网或 HTTPS 页面中通常需要部署为 `wss://`。

### 控制方连接

不携带 `tid` 参数连接 V4 服务时，该连接会被视为控制方：

```text
ws://127.0.0.1:9998
```

连接成功后，服务端返回：

```json
{
  "type": "hello",
  "clientId": "控制方 clientId"
}
```

其中 `clientId` 用于被控方接入。

### 被控方连接

被控方通过 `tid` 指定控制方：

```text
ws://127.0.0.1:9998?tid=控制方clientId
```

连接建立后，被控方同样会先收到 `hello` 帧。接入成功后，被控方会收到：

```json
{
  "type": "controller_attached",
  "clientId": "控制方 clientId"
}
```

控制方会收到：

```json
{
  "type": "client_attached",
  "clientId": "被控方 clientId"
}
```

控制方断开时，被控方会收到 `controller_disconnected` 并被关闭；被控方断开时，控制方会收到：

```json
{
  "type": "client_disconnected",
  "clientId": "被控方 clientId"
}
```

### WebSocket 消息

控制方向指定被控方发送消息：

```json
{
  "type": "message",
  "clientId": "被控方 clientId",
  "data": {
    "op": "example",
    "value": 1
  }
}
```

被控方会收到：

```json
{
  "type": "message",
  "data": {
    "op": "example",
    "value": 1
  }
}
```

被控方向控制方上报消息：

```json
{
  "type": "message",
  "data": {
    "op": "report",
    "value": 1
  }
}
```

控制方会收到：

```json
{
  "type": "message",
  "clientId": "被控方 clientId",
  "data": {
    "op": "report",
    "value": 1
  }
}
```

### V4 错误码

| 错误 | 说明 |
| --- | --- |
| `bad_request` | 消息格式错误 |
| `client_not_found` | 被控方不存在或不在线 |
| `controller_not_found` | 被控方指定的控制方不存在 |

### V4 断开码

| 断开码 | 说明 |
| --- | --- |
| `4000` | 控制方断开，被控方被关闭 |
| `4001` | 被控方指定的控制方不存在 |
| `4002` | 控制方长时间没有被控方接入，空闲超时 |

## V3 协议

V3 为旧协议，采用两个 WebSocket 连接配对的模式：

```text
第三方控制端 <-> WebSocket Server <-> DG-LAB APP 终端
```

### V3 消息流程

V3 服务维护一组控制方与 APP 端的配对关系：

```text
1. 控制端与 APP 端分别连接 ws://host:9999
2. 服务端分别返回 bind 帧，告知各自 clientId
3. 控制端发送 bind，将自己的 clientId 与 APP 端 clientId 绑定
4. 绑定成功后，控制端下发强度、清除、波形或自定义消息
5. APP 端上报 feedback-* 或 strength-* 时，服务端转发给控制端
6. 任意一端断开时，服务端通知另一端 break 并关闭配对连接
```

V3 的所有业务消息都围绕这四个字段：

| 字段 | 说明 |
| --- | --- |
| `type` | 消息类型，决定服务端如何处理 |
| `clientId` | 控制端 ID |
| `targetId` | APP 端 ID |
| `message` | 消息内容，可能是业务指令、波形数据或 APP 回传 |

### 连接

客户端连接到 V3 服务后，服务端会立即返回当前连接的 `clientId`：

```json
{
  "type": "bind",
  "clientId": "当前连接 ID",
  "targetId": "",
  "message": "targetId"
}
```

后续消息都需要携带：

| 字段 | 说明 |
| --- | --- |
| `clientId` | 发送方 ID |
| `targetId` | 目标 ID |
| `type` | 消息类型 |
| `message` | 消息内容 |

### 绑定

控制端拿到 APP 端 `clientId` 后，发送绑定消息：

```json
{
  "type": "bind",
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "message": "targetId"
}
```

绑定成功时，双方会收到：

```json
{
  "type": "bind",
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "message": "200"
}
```

### 强度控制

`type` 为 `1`、`2`、`3` 时，服务端会转换为 DG-LAB APP 可识别的强度消息：

| `type` | 说明 |
| --- | --- |
| `1` | 减少强度 |
| `2` | 增加强度 |
| `3` | 按 `strength` 调整强度 |

```json
{
  "type": 3,
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "channel": "A",
  "strength": 20,
  "message": "strength"
}
```

通道支持 `1` / `A` / `a` 与 `2` / `B` / `b`。

服务端实际转发给 APP 的消息如下：

| 控制端消息 | 服务端转发给 APP | 说明 |
| --- | --- | --- |
| `type: 1` | `strength-通道+0+1` | 减少指定通道强度 |
| `type: 2` | `strength-通道+1+1` | 增加指定通道强度 |
| `type: 3` | `strength-通道+2+strength` | 设置指定通道强度 |

### 指定强度与清除

`type` 为 `4` 时，可设置指定通道强度：

```json
{
  "type": 4,
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "channel": "A",
  "strength": 30,
  "message": "strength"
}
```

清除通道：

```json
{
  "type": 4,
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "channel": "A",
  "message": "clear"
}
```

`type: 4` 会根据 `message` 内容转换：

| 控制端消息 | 服务端转发给 APP | 说明 |
| --- | --- | --- |
| `message` 包含 `clear` | `clear-通道` | 清除指定通道波形 |
| `message` 不包含 `clear` | `strength-通道+2+strength` | 设置指定通道强度 |

### 波形消息

`type` 为 `clientMsg` 时，服务端会按配置把波形帧拆成多个 `pulse-` 包，定时向 APP 端发送。

```json
{
  "type": "clientMsg",
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "channel": "A",
  "time": 5,
  "message": "波形数据"
}
```

发送完成后，控制端会收到：

```json
{
  "type": "notify",
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "message": "发送完毕"
}
```

同一控制端、同一通道有正在发送的波形时，新波形会覆盖旧波形，并先向 APP 端发送清除指令。

标准波形格式为 `A:[...]` 或 `B:[...]`，数组中的每个 16 位十六进制帧按 `100ms` 计算。服务端会把输入帧循环补齐或截断到 `time` 指定的总时长，然后按环境变量拆包发送：

```text
总帧数 = time * 10
发送包数 = DEFAULT_PUNISHMENT_TIME * time
发送间隔 = 1000 / DEFAULT_PUNISHMENT_TIME ms
每包帧数 ≈ 10 / DEFAULT_PUNISHMENT_TIME
```

如果 `DEFAULT_PUNISHMENT_TIME` 大于 `10`，服务端会按每帧最小 `100ms` 将有效发送频率限制为 `10` 次/秒。无法解析为标准波形数组的历史自定义字符串仍会按原始内容透传重复发送。

应用层建议通过 `dglab-kit` 的 `sendPulse` 使用内置波形数据，由 SDK 负责序列化，避免手写十六进制帧导致 APP 无法解析。

### V3 APP 回传

APP 端回传的 `message` 以 `feedback` 或 `strength` 开头时，服务端会直接转发给控制端：

```json
{
  "type": "msg",
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "message": "feedback-1"
}
```

```json
{
  "type": "msg",
  "clientId": "控制端 clientId",
  "targetId": "APP 端 clientId",
  "message": "strength-1+2+20"
}
```

控制端可以用这些回传更新 UI，例如按钮反馈、强度同步或状态提示。

### V3 二维码

DG-LAB 4 APP 的 Socket 控制 V3 二维码可以由控制方 `targetId` 拼接生成：

```ts
const wsUrl = `wss://your-domain.example/${targetId}`;
const qrcode = `https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#${encodeURIComponent(wsUrl)}`;
```

本地开发可以使用 `ws://127.0.0.1:9999/...` 测试；公网或 HTTPS 页面中通常需要部署为 `wss://`。

### 心跳

服务端会定时向所有在线连接发送：

```json
{
  "type": "heartbeat",
  "clientId": "当前连接 ID",
  "targetId": "已配对目标 ID",
  "message": "200"
}
```

客户端发送 `type=heartbeat` 的消息时，服务端会忽略该消息，不再额外转发。

### V3 错误码

| 错误码 | 说明 |
| --- | --- |
| `400` | 连接已被绑定 |
| `401` | 绑定目标无效，或不能绑定自己 |
| `402` | 双方未建立配对关系 |
| `403` | 消息格式错误 |
| `404` | 目标不存在，或消息来源非法 |
| `406` | 通道参数错误 |

断开连接时，服务端会通知配对方：

```json
{
  "type": "break",
  "clientId": "配对方 clientId",
  "targetId": "断开方 clientId",
  "message": "209"
}
```

## 项目结构

```text
dglab-websocket-server/
├── README.md
├── .env.example
├── package.json
├── tsconfig.json
├── v3-server.ts
└── v4-server.ts
```
