/**
 * 新手引导定义（数据驱动：新增"引导 N"只需加一张表，引擎复用）。
 * anchor = 稳定锚点（data-tour 属性），UI 大改时锚点跟着元素走，指引无需重做；
 * 锚点找不到时引擎会自动跳过该步（容错）。
 */

export interface TourStep {
  /** 定位锚点（CSS 选择器，建议 data-tour 属性）；空 = 无高亮（如完成页） */
  anchor: string;
  title: string;
  body: string;
  /** 该步需要停留的视图；与当前不符时引擎自动切换 */
  view?: "control" | "settings";
  /** 浮窗相对高亮框的位置（默认底部居中；right=靠右，top=顶部） */
  side?: "bottom" | "top" | "right";
}

export interface Tour {
  /** 独立 id，localStorage 记忆键用 */
  id: string;
  steps: TourStep[];
}

/** 引导 1：新手三步（配置 AI → 配对 → 自动运行 → 急停） */
export const TOURS: Tour[] = [
  {
    id: "guide1",
    steps: [
      {
        anchor: "[data-tour='settings-btn']",
        title: "第一步：配置 AI",
        body: "点右上角「设置」，先完成 AI 模型配置。",
        view: "control",
      },
      {
        anchor: "[data-tour='api-key']",
        title: "粘贴 API Key",
        body: "填服务商给你的真实密钥（官方 DeepSeek 开放平台可创建）。",
        view: "settings",
      },
      {
        anchor: "[data-tour='base-url']",
        title: "填 API 接口地址",
        body: "填 API 接口地址，不是网页首页。\n官方示例：https://api.deepseek.com",
        view: "settings",
      },
      {
        anchor: "[data-tour='model']",
        title: "填模型名",
        body: "地址、密钥、模型名要属于同一服务。\n官方示例：**deepseek-v4-flash-vision-exp**",
        view: "settings",
      },
      {
        anchor: "[data-tour='test-btn']",
        title: "先测试连接",
        body: "点「测试连接」，通过后再保存。",
        view: "settings",
      },
      {
        anchor: "[data-tour='save-btn']",
        title: "保存并生效",
        body: "保存即生效。",
        view: "settings",
      },
      {
        anchor: "[data-tour='pair-qr']",
        title: "配对郊狼",
        body: "手机连同一 Wi-Fi，用 DG-LAB 4.0 App 扫码；配对后在 App 里关闭「屏蔽输出」，否则设备不会有感觉。",
        view: "control",
      },
      {
        anchor: "[data-tour='autopilot']",
        title: "打开自动运行",
        body: "AI 开始自动观察、发言、动设备；摄像头/麦克风跟随它启停。",
        view: "control",
      },
      {
        anchor: "[data-tour='estop']",
        title: "记住急停",
        body: "长按空格 1 秒，或点这个按钮，全部停止。",
        view: "control",
        side: "right", // 急停在底部居中，浮窗往右偏移避免遮挡
      },
      {
        anchor: "[data-tour='help-btn']",
        title: "完成",
        body: "需要更丰富的体验？点顶栏「帮助」，进阶指引即将上线喵~",
        view: "control",
        side: "right", // 和第 9 步一致，浮窗往右偏移
      },
    ],
  },
];
