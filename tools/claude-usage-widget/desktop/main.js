// Claude 用量液體槽 —— Electron 桌面掛件主程式。
// 透明、無邊框、永遠最上層、可拖曳、記住位置。讀雲端 usage.json(與網頁同源資料)。
const { app, BrowserWindow, ipcMain, screen, Notification } = require('electron');
const fs = require('fs');
const path = require('path');

// 關掉 GPU 硬體加速 —— 這是壓 GPU 佔用的關鍵一刀。
// 透明+永遠最上層的 Electron 視窗每一幀都要 GPU 合成一次,對這種只有幾塊小 canvas
// 的迷你掛件來說,改走 CPU 軟體渲染反而讓本進程 GPU 佔用→0,而 CPU 成本可忽略。
// 必須在 app ready 之前呼叫。
app.disableHardwareAcceleration();

// Windows 通知要有 AppUserModelID 才會正確顯示來源/不被吞掉。
if (process.platform === 'win32') app.setAppUserModelId('com.sml.claude-usage');

const STATE_FILE = () => path.join(app.getPath('userData'), 'window-state.json');
const DEFAULT_BOUNDS = { width: 560, height: 380 };

function loadBounds() {
  try {
    const b = JSON.parse(fs.readFileSync(STATE_FILE(), 'utf8'));
    if (b && b.width > 200 && b.height > 150) return b;
  } catch (_) {}
  return null;
}
function saveBounds(win) {
  try {
    if (!win || win.isDestroyed()) return;
    fs.writeFileSync(STATE_FILE(), JSON.stringify(win.getBounds()));
  } catch (_) {}
}

let win;
function createWindow() {
  const saved = loadBounds();
  const bounds = saved || (() => {
    // 預設放在主螢幕右上角
    const wa = screen.getPrimaryDisplay().workArea;
    return {
      width: DEFAULT_BOUNDS.width,
      height: DEFAULT_BOUNDS.height,
      x: wa.x + wa.width - DEFAULT_BOUNDS.width - 24,
      y: wa.y + 24,
    };
  })();

  win = new BrowserWindow({
    ...bounds,
    minWidth: 320,
    minHeight: 220,
    frame: false,
    transparent: true,
    resizable: true,
    hasShadow: false,
    alwaysOnTop: true,
    skipTaskbar: false,
    backgroundColor: '#00000000',
    title: 'Claude用量',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false, // 允許跨網域 fetch 雲端 usage.json(本機受信任 App)
    },
  });

  // 浮在幾乎所有視窗之上(含全螢幕以外)
  win.setAlwaysOnTop(true, 'screen-saver');
  win.loadFile(path.join(__dirname, 'renderer.html'));

  let t;
  const persist = () => { clearTimeout(t); t = setTimeout(() => saveBounds(win), 400); };
  win.on('move', persist);
  win.on('resize', persist);
  win.on('close', () => saveBounds(win));
}

ipcMain.on('app-quit', () => app.quit());
ipcMain.on('minimize', () => { if (win && !win.isDestroyed()) win.minimize(); });
ipcMain.on('toggle-top', (_e, on) => { if (win) win.setAlwaysOnTop(!!on, 'screen-saver'); });

// 背景工作完成 → 桌面原生通知(這就是「主動叫你」)。點通知把掛件叫到最前。
ipcMain.on('notify', (_e, p) => {
  try {
    if (!Notification.isSupported()) return;
    const n = new Notification({ title: (p && p.title) || 'Claude', body: (p && p.body) || '', silent: false });
    n.on('click', () => { if (win && !win.isDestroyed()) { win.show(); win.focus(); } });
    n.show();
  } catch (_) {}
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
