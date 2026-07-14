# 天王里里長助理選舉 — 設計稿 / Codex 交接

甜甜 bot 上的匿名選舉系統。一指令開場、全按鈕流程；當選者自動綁定身分組。

- 伺服器(guild)：`698760345660948530`
- 當選綁定身分組：`877894550570565642`（天王里里長助理，pos 114）
- 投票資格身分組：`872861844388335617`（天王里里民）
- 甜甜 bot：`909624656846286899`，具 `甜甜` 身分組(ADMIN+管理身分組)、最高身分組 pos 150 → **綁得動目標身分組(已驗)**

---

## 1. 匿名機制（本案核心）

**強度 A：對其他用戶匿名，管理者可逐票稽核。**

鐵律（實作必守，否則匿名破功）：
- **所有投票互動一律 ephemeral**（`flags: 64` / `MessageFlags.Ephemeral`），含 `deferReply({ ephemeral:true })`。
- 公開頻道**永不**出現「誰投票 / 誰投給誰」任何訊息或通知。
- **不用 emoji reaction 收票**（反應公開，任何人可查投票者）。
- 投票期間公開面板**隱藏票數**（顯示「投票中，開票後公布」），避免帶風向。
- 票只存進自家 DynamoDB；其他用戶對 DB 零存取 → 天然查不到。管理者透過 `!選舉稽核` 專用指令才看得到明細。

## 2. 選舉階段（狀態機）

`nomination`(報名) → `signature`(連署，與報名並行) → `voting`(投票) → `closed`(開票完)

階段轉換由管理者指令觸發（見 §6）。

## 3. 報名參選管線（候選人視角，全按鈕）

1. 報名期，公開面板按 **「📝 我要參選」**
2. 彈出 **Modal 表單**：口號(必)、政見一句(必)、參選宣言(選)
3. **上傳參選照片** — Modal 塞不了圖，故：Modal 送出後，甜甜以 ephemeral 指示「把照片貼到本頻道或私訊甜甜」；bot 用 messageCreate 監聽器，抓「已登記報名者」的下一張圖片附件。
4. **繳保證金 500🦷** — ephemeral 確認 → 扣牙齒（走現有牙齒經濟 `changePoint`）。得票率 ≥10% 全額退還，否則沒收。
5. **選文宣風格** — 甜甜用照片+口號一次生成 A/B/C/M 四款預覽，ephemeral 按鈕讓參選人挑一款（見 §5）。
6. 進入**連署階段**：面板顯示各候選人連署進度條，里民按「🤝 連署 XXX」。連署 **≥5 位里民** → 正式候選資格 ✅。
7. 管理者可隨時審核/剔除候選人。報名截止 → 甜甜結算正式候選名單 → 進投票期。

> 連署=公開造勢（顯示人數/進度條，連署人**名單**只有管理者查得到，一般人只看到數字）；投票=完全匿名。兩者不衝突。

## 4. 投票 / 開票 / 綁身分組

- 公開面板按 **「🗳️ 去投票」**(customId `elec_vote:<electionId>`) → ephemeral 候選人下拉選單(`elec_pick:<electionId>`) → conditional write 防重複投票 → ephemeral「✅ 已投給 X，沒人看得到你投給誰」。非里民按 → ephemeral「限天王里里民投票」。
- 開票 `!選舉開票 <id>`(管理者)：phase→closed → 統計 → **卸掉所有現任「天王里里長助理」持有者、同時改掛「前任里長助理」榮譽徽章 → 再把「里長助理」掛給當選者** → 公告 embed（結果+總票數，不含個別明細）。
- **前任里長助理徽章**(`formerRole`)：卸任者不是失去一切，而是換成一個**無權限、純收藏感**的榮譽身分組（像掛勳章、可累積多屆）。此身分組已建立：role_id **`1526441135881326614`**、無任何權限、古銅金色(#CD7F32)。
- **任期到期自動卸**(`termExpiry` 預設 **on**)：若設了任期期限，到期即使沒有新選舉，也自動把現任卸為「前任里長助理」徽章（甜甜定時檢查）。
- **法定投票門檻（quorum）**：開票時先算 `門檻票數 = ceil(天王里里民身分組即時成員數 × 35%)`。**總投票數 ≥ 門檻 才成案**；未達 → **本屆流選**：不綁任何身分組、公告「投票率未達門檻（里民×35%），本屆從缺」，由管理者決定是否重辦。（門檻比的是**投票率/總票數**，不是當選者個人得票。）
- 平手：**公告平手、由管理者裁定**（不自動決定）。

## 5. 文宣自動生成器（已做好模板，在 `poster/`）

技術：**HTML 模板 + Playwright 截圖 + Noto Sans CJK**（同 plate-daily「程式浮凸」路線）。候選人只給「照片 + 口號」，其餘（番號/姓名/職稱/懇請賜票/政黨色）程式合成。

四款風格(參選人自選)：
| 檔案 | 風格 | 尺寸 |
|---|---|---|
| `style_A_redgold.html` | 熱血紅金(綬帶勳章+放射光) | 600×820 直式 |
| `style_B_skyblue.html` | 清新藍白(乾淨改革) | 600×820 直式 |
| `style_C_grassroots.html` | 本土草根(稻穗綠金) | 600×820 直式 |
| `style_M_modern.html` | 現代方形(社群模版+政見打勾) | 720×720 方形 |

現代方形風(M)另長出**多用途版型系統**(同一設計語言、依用途出版)：
| 檔案 | 用途 |
|---|---|
| `modern_M1.html` | 形象照(自我介紹) |
| `modern_M2.html` | 政績(打勾清單) |
| `modern_M3.html` | 政策推廣(單一主張大字) |
| `modern_M4.html` | 懇請支持(催票+投票日 CTA) |
參選人選定風格後，甜甜可依用途各生一版。

資料欄位(Codex 需模板化)：`番號` `姓名` `職稱` `口號` `照片路徑`；M2 另有政績清單、M3 有政策主張+說明、M4 有投票日。目前模板寫死示範值(阿明/①/牌品好人品才好)，Codex 改成注入。

**🛡️ 出圖前防呆閘門(不可省)**：`check.js` — 載入渲染結果、量測所有含文字元素的 bounding box、兩兩比對相交，**有重疊即報錯擋下**。`render.js` 已示範「截圖後立即自動驗」。凡生成文宣**必過此閘門才放行**。
- 已知地雷：重疊幾乎都來自 `position:absolute` 浮貼；改用 flex 流式排版(直欄/橫列互相推開)即免疫。B 版原本就是絕對定位 `.plea` 壓到姓名，已改流式修好。
- 環境：`FONTCONFIG_FILE=/home/smlbot/.fonts/fonts.conf`、Playwright 路徑見 render.js、emoji 需 `Noto Color Emoji`(已裝 ~/.fonts)。

## 5b. 後台管理頁（甜甜遊戲館）

所有規則**後台可調、不寫死**。後台建在甜甜遊戲館 `sweetbot-games.web.app`。

**接線方式**（沿用站上既有慣例，如 vote_manager / random_event_manager / trialgate_admin）：
- 新頁：`/opt/sml/sweetbot-site/public/election_admin.html`
- 掛進 index：在 `public/index.html` 的 `PAGES` 陣列補一筆
  `{ icon:'🗳️', title:'天王里選舉', page:'election_admin.html', desc:'選舉時程／報名條件／候選人審核／開票，存 DynamoDB 甜甜即時讀取。', badge:'b-live', badgeText:'🔧 後台' }`
- 部署：`bash /opt/sml/sweetbot-site/deploy.sh`（先 `check-conflict.sh`；只部 sweetbot target，絕不碰計分後台）
- 存取控管：站上 Google 登入 + 工作人員白名單（既有機制）
- 資料流：後台寫 `election-config`(DDB) → 甜甜即時讀取，與 §7 各表配合

**後台可控欄位 + 預設值：**

① 時程：報名開始/截止、投票開始/截止、`autoTally`(投票截止自動開票，預設 on)。連署期預設**與報名期並行**(報名截止=連署截止)。

② 參選資格：`candidateRole`(預設天王里里民)、`deposit`(500🦷)、`refundThreshold`(得票率 10% 退還)、`signatureQuota`(**5，首屆不放寬**)、`allowWithdraw`(預設 on，退保證金)、`maxCandidates`(預設無上限)。**沒收處理**：未達退還門檻的保證金**直接燒掉(sink，不進獎池、不重分配)**，`changePoint` 只記一筆扣除。

③ 投票：`voterRole`(天王里里民)、`allowRevote`(截止前可改票，預設 on)、`seats`(1)、`quorumPct`(**法定投票門檻，預設 35%**：總投票數 ≥ ceil(里民即時成員數×35%) 才成案，未達流選/從缺，見 §4)、平手→管理者裁定。

④ 結果綁定：`winnerRole`(里長助理 877894550570565642)、`formerRole`(前任里長助理榮譽徽章 **`1526441135881326614`**，已建/無權限/古銅金)、`replaceIncumbent`(先卸現任並改掛徽章、預設 on)、`termExpiry`(任期到期自動卸為徽章，預設 **on**)、`termDays`(任期長度，**預設 90 天＝選舉週期三個月一輪**)。

⑤ 文宣：`enabledStyles`(A/B/C/M 全開)、`enabledLayouts`(M1~M4)。

⑥ 候選人審核：後台可看報名清單、審核/剔除候選人、看連署進度、開票後看結果（稽核明細 §1 走管理者專用途徑）。

## 6. 指令總表（管理者）

- `!選舉開始 <標題>` → 建選舉(nomination)、發公開面板
- `!選舉候選人 add/remove @user` → 增刪候選人
- `!選舉投票開始 <id>` → phase→voting、面板更新、設截止時間
- `!選舉開票 <id>` → 統計+綁身分組+公告
- `!選舉稽核 <id>` → **僅管理者**，回傳 userId→候選人 明細（ephemeral 或私訊）

## 7. 資料表（DynamoDB，沿用現有 DAO 慣例）

- `election-meta`：PK=electionId。{guildId, roleId, voterRoleId, title, phase, votingDeadline, createdBy, winnerId}
- `election-candidate`：PK=electionId, SK=userId。{name, slogan, policy, manifesto, photoUrl, style(A/B/C/M), posterUrl, deposit, signatureCount, official(bool), ballotNo}
- `election-signature`：PK=electionId#candidateId, SK=voterId。（連署防重複）
- `election-vote`：PK=electionId, SK=voterId。{candidateId, votedAt} ← **plan A：userId→票，管理者可稽核，conditional put 防重複**

## 8. 前置/地雷

- 甜甜綁身分組權限已驗證 OK（§0）。
- 照片上傳：Discord Modal 不收圖，須用 messageCreate 監聽抓附件（設短時窗+只認已登記報名者，避免誤抓）。
- **照片審查政策（定案）**：**不做自動/事前不雅偵測**；不雅風險由**管理者手動汰除成員＋刪除圖片**善後（後台 §5b⑥ 剔除候選人時一併清除其 photoUrl/文宣圖）。
- 牙齒經濟：保證金走現有 `changePoint` 流水帳，退款/沒收都要記帳（**沒收＝直接燒掉當 sink，不進獎池**）。
- 一指令開場後全走互動按鈕/選單，面板同訊息重繪不洗版（範本 InBetween.js）。

## 9. 驗收點

1. 非里民無法投票；里民投票全程 ephemeral、公開頻道零痕跡。
2. 同一人重複投票被 conditional write 擋下。
3. `!選舉稽核` 僅管理者可用、能正確列出 userId→候選人。
4. 報名管線：Modal→照片→保證金→選風格→連署達標入場，五步串通；保證金正確扣/退。
5. 文宣生成：四款皆可生，且**每張都過 check.js 零重疊**（含長名字不爆版）。
6. 開票：正確統計、先卸舊持有者再掛當選者、平手時停手待裁定、公告只露總票數。
7. **法定門檻**：總投票數 < ceil(里民×35%) → 判流選/從缺、不綁身分組、公告「投票率未達門檻」；達標才成案。門檻依開票當下里民即時人數計算。
8. **保證金沒收**：未達 10% 退還門檻者，扣除的 500🦷 直接燒掉（記一筆 `changePoint` 扣除，無任何回流）。
9. **任期到期**：`termExpiry` on 時，當選滿 `termDays`(預設 90) 即使無新選舉，現任自動卸為「前任里長助理」徽章。

## 💰 成本控管（遵循 tools/COST_CONTROL.md）

- **成本來源**：新 DDB 表（`election-config` ＋ §7 各投票/報名表）＋後台 admin Lambda；候選人報名照片存自控圖床 `boyplaymj-image`。量級極小（PAY_PER_REQUEST；照片單張、活動性流量，預估 < $1/月）。
- 所有新表 **PAY_PER_REQUEST**（沿用現有 DAO 慣例，§7）；保證金走既有 `changePoint` 流水帳，**不新增計費系統**。
- 文宣海報四款走**本機 Playwright 程式合成**（HTML→截圖），在 sml-claude-bot 上跑，**不燒 LLM／不打生圖 API**。
- **無 LLM／無付費 API**，故免「帳本表＋月度封頂」四件套。
