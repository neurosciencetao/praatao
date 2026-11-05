# 17 - 用 Parselmouth 核对知识库里的数字

> 目的：知识库里有不少具体的数字（75 Hz、0.025 秒、5500 Hz、1 W/m^2 等）。这些数字如果错了，学生照着做就会得到错误的结论。本文用 **Parselmouth**（`praat-parselmouth` 0.4.7，直接绑定 Praat 自己的 C/C++ 程式码）把每一个量重新算一遍，再跟字典对照。

被检验的声音档：`prototypes/v0/assets/demo_vowel.wav`，16 kHz、0.8 秒的合成元音。主档 elements.yaml 有 288 个条目，片段档另有 155 个副本，原始合计 443 个，合并之后的实际条目数是 288。

测量全部离线完成，不碰正在运行的 Praat。命令：`python tools\parselmouth_check.py`。

## 1. 结论先讲

共核对 13 条主张，全部成立。其中有 8 条在这次核对之前写错了，已经就地改好：

| 改掉的错误 | 改成 |
| --- | --- |
| 强度是「以被分析讯号里最安静的部分为基准」 | 以听觉阈值为基准（0 dB 是 2e-5 Pa） |
| Get intensity (dB) 以 1 W/m^2 为基准 | 以 1e-12 W/m^2 为基准 |
| To Intensity 的预设最低基频是 75 Hz | 是 100 Hz |
| 预设最低基频会让强度曲线出现音高周期波纹 | 下限设得比说话者的基频还高才会出现 |
| 75 到 600 Hz 会对 F0 超过 300 Hz 的声音八度跳错 | 八度跳错从上限开始，实测 600 Hz 才发生 |
| 共振峰上限 5500 Hz 适合儿童、3000 Hz 适合成年男性 | 5500 Hz 适合成年女性、5000 Hz 适合成年男性、8000 Hz 适合幼童 |
| 极点数目每 1000 Hz 一个，所以 5500 Hz 要 5 到 6 个 | 共振峰数目每 1000 Hz 一个，Praat 预设 5 个，每个共振峰用两个极点 |
| 用 5500 Hz 上限追男声，共振峰会落进杂讯 | 低频区的共振峰会消失，Praat 的问答说上限要降到 5000 Hz |

## 2. 核对表

| 主张 | 来源条目 | 实测值 | 判定 |
| --- | --- | --- | --- |
| To Intensity 的 dB 基准是听觉阈值（2e-5 Pa），不是被分析讯号里最安静的那一段 | ow-to-intensity, workflow-intensity, get-intensity, intensity-object, type-intensity | 峰值 83.38 dB；20*log10(rms/2e-5) = 83.02 dB；10*log10(I/1e-12) = 83.02 dB；前面加 0.4 秒静音后仍是 83.38 dB | 成立 |
| 一般说话声的峰值强度落在 80 到 100 dB 之间 | ow-to-intensity, workflow-intensity | 83.4 dB（样音峰值振幅 0.665） | 成立 |
| Get intensity (dB) 的参考基准是 1e-12 W/m^2，也就是听觉阈值 | get-intensity-db | Get intensity (dB) 读出 83.02 dB；等于 20*log10(rms/2e-5) = 83.02 dB；若以 1 W/m^2 为基准则是 -36.98 dB | 成立 |
| To Pitch... 的预设下限是 75 Hz，上限是 600 Hz | to-pitch, pitch-settings, ow-analyse-periodicity, workflow-pitch | Parselmouth 介面默认值 pitch_floor=75.0, pitch_ceiling=600.0；产生出来的 Pitch 物件 ceiling = 600 Hz | 成立 |
| 八度跳错从上限开始：上限 600 Hz 时，基频碰到 600 Hz 就会被报成一半 | pitch-settings, to-pitch | 300 Hz -> 300 Hz；400 Hz -> 400 Hz；500 Hz -> 500 Hz；600 Hz -> 300 Hz（错）；700 Hz -> 350 Hz（错）；800 Hz -> 400 Hz（错） | 成立 |
| 奈奎斯特上限等于采样率的一半，16 kHz 的档案上限是 8 kHz | concept-nyquist-limit, concept-sampling-frequency, get-sampling-frequency, ow-convert, resample | 采样率 16000 Hz，一半是 8000 Hz；Spectrum 物件的频率上限 xmax = 8000 Hz | 成立 |
| Gaussian 窗的 -3 dB 频宽约等于 1.3 除以窗长，0.025 秒的窗约合 50 Hz | spectrogram-window-length, ow-analyse-spectrum, to-spectrogram | 5 ms 窗实测 258 Hz，公式 1.298/窗长 = 260 Hz；25 ms 窗实测 52 Hz，公式 1.298/窗长 = 52 Hz；30 ms 窗实测 44 Hz，公式 1.298/窗长 = 43 Hz | 成立 |
| 共振峰上限 5500 Hz 适合成年女性，成年男性约 5000 Hz，幼童约 8000 Hz | to-formant-burg, formant-settings, workflow-formant | 上限 3000 Hz：F1=298 Hz(频宽226), F2=701 Hz(频宽2), F3=1174 Hz(频宽11), F4=1220 Hz(频宽6)；上限 5000 Hz：F1=696 Hz(频宽10), F2=1107 Hz(频宽268), F3=1206 Hz(频宽6)；上限 5500 Hz：F1=695 Hz(频宽8), F2=1065 Hz(频宽195), F3=1206 Hz(频宽4), F4=4080 Hz(频宽1852)；上限 3000 Hz 时最低的那个极点掉到 298 Hz（频宽 226 Hz），是典型的伪极点 | 成立 |
| 共振峰的数目大约每 1000 Hz 一个，Praat 在 5500 Hz 的范围里预设 5 个 | formant-settings, to-formant-burg | 要求 5 个共振峰时 Praat 在 0.4 秒处给出 4 个：F1, F2, F3, F4；Praat 每个共振峰用两个极点，所以 5 个共振峰是 10 个极点 | 成立 |
| 共振峰必须在奈奎斯特上限之下才谈得上有意义 | concept-formant, to-formant-burg, formant-settings | 奈奎斯特上限 8000 Hz；实测 F1=695 Hz, F2=1065 Hz, F3=1206 Hz, F4=4080 Hz | 成立 |
| 字典对 F1/F2 没有写数值范围，只说明 F1 对应口腔开度、F2 对应舌位 | concept-formant, formant-object | F1=695 Hz，F2=1065 Hz，F3=1206 Hz；字典没有写 F1/F2 的数值范围，只说 F1 与口腔开度有关、F2 与舌位有关 | 成立 |
| To Intensity... 对话框的预设最低基频是 100 Hz | ow-to-intensity, workflow-intensity, type-intensity | Parselmouth 介面默认值 minimum_pitch = 100.0（对应 Praat 对话框里的 Pitch floor (Hz)） | 成立 |
| 最低基频设得比说话者的基频还高时，强度曲线才会出现音高周期的波纹 | ow-to-intensity, workflow-intensity, type-intensity | 下限 75 Hz 时峰峰值 0.0032 dB；下限 100 Hz 时峰峰值 0.0069 dB；下限 300 Hz 时峰峰值 0.1837 dB；下限 400 Hz 时峰峰值 0.3526 dB。参考：Praat 手册说下限设太高会出现音高同步的强度起伏，设太低则曲线被抹平 | 成立 |

## 3. 每一条怎么量的

### To Intensity 的 dB 基准是听觉阈值（2e-5 Pa），不是被分析讯号里最安静的那一段

* 来源条目：ow-to-intensity, workflow-intensity, get-intensity, intensity-object, type-intensity
* 实测值：峰值 83.38 dB；20*log10(rms/2e-5) = 83.02 dB；10*log10(I/1e-12) = 83.02 dB；前面加 0.4 秒静音后仍是 83.38 dB
* 判定：**成立**
* 说明：Praat 的原始码把强度写成 10*log10(强度 / 2e-5 Pa)，所以加不加静音都不会改变同一段讯号的数值。字典原本写「以被分析讯号中最安静的部分为参考基准」，那是错的。

### 一般说话声的峰值强度落在 80 到 100 dB 之间

* 来源条目：ow-to-intensity, workflow-intensity
* 实测值：83.4 dB（样音峰值振幅 0.665）
* 判定：**成立**
* 说明：样音 demo_vowel.wav 的峰值是 83.4 dB，落在这一段里。

### Get intensity (dB) 的参考基准是 1e-12 W/m^2，也就是听觉阈值

* 来源条目：get-intensity-db
* 实测值：Get intensity (dB) 读出 83.02 dB；等于 20*log10(rms/2e-5) = 83.02 dB；若以 1 W/m^2 为基准则是 -36.98 dB
* 判定：**成立**
* 说明：Praat 的原始码用 10*log10(均方 / 4e-10)，4e-10 就是 (2e-5 Pa)^2。字典原本写「以 1 W/m^2 为参考基准」，差了 12 个数量级。

### To Pitch... 的预设下限是 75 Hz，上限是 600 Hz

* 来源条目：to-pitch, pitch-settings, ow-analyse-periodicity, workflow-pitch
* 实测值：Parselmouth 介面默认值 pitch_floor=75.0, pitch_ceiling=600.0；产生出来的 Pitch 物件 ceiling = 600 Hz
* 判定：**成立**
* 说明：Praat 手册也写明 Pitch floor 75 Hz、Pitch ceiling 600 Hz。

### 八度跳错从上限开始：上限 600 Hz 时，基频碰到 600 Hz 就会被报成一半

* 来源条目：pitch-settings, to-pitch
* 实测值：300 Hz -> 300 Hz；400 Hz -> 400 Hz；500 Hz -> 500 Hz；600 Hz -> 300 Hz（错）；700 Hz -> 350 Hz（错）；800 Hz -> 400 Hz（错）
* 判定：**成立**
* 说明：量到的转折点就在上限本身，上限之内没有跳错，75 Hz 的下限更不是问题所在。字典原本写「F0 超过 300 Hz 的男声」，300 这个数字没有根据。

### 奈奎斯特上限等于采样率的一半，16 kHz 的档案上限是 8 kHz

* 来源条目：concept-nyquist-limit, concept-sampling-frequency, get-sampling-frequency, ow-convert, resample
* 实测值：采样率 16000 Hz，一半是 8000 Hz；Spectrum 物件的频率上限 xmax = 8000 Hz
* 判定：**成立**
* 说明：Praat 自己的 Spectrum 物件也把频率上限设在 8000 Hz。

### Gaussian 窗的 -3 dB 频宽约等于 1.3 除以窗长，0.025 秒的窗约合 50 Hz

* 来源条目：spectrogram-window-length, ow-analyse-spectrum, to-spectrogram
* 实测值：5 ms 窗实测 258 Hz，公式 1.298/窗长 = 260 Hz；25 ms 窗实测 52 Hz，公式 1.298/窗长 = 52 Hz；30 ms 窗实测 44 Hz，公式 1.298/窗长 = 43 Hz
* 判定：**成立**
* 说明：Praat 手册给的常数是 1.2982804，0.025 秒的窗就是 51.9 Hz；另外共振峰分析实际用的窗长是这个设定值的两倍。

### 共振峰上限 5500 Hz 适合成年女性，成年男性约 5000 Hz，幼童约 8000 Hz

* 来源条目：to-formant-burg, formant-settings, workflow-formant
* 实测值：上限 3000 Hz：F1=298 Hz(频宽226), F2=701 Hz(频宽2), F3=1174 Hz(频宽11), F4=1220 Hz(频宽6)；上限 5000 Hz：F1=696 Hz(频宽10), F2=1107 Hz(频宽268), F3=1206 Hz(频宽6)；上限 5500 Hz：F1=695 Hz(频宽8), F2=1065 Hz(频宽195), F3=1206 Hz(频宽4), F4=4080 Hz(频宽1852)；上限 3000 Hz 时最低的那个极点掉到 298 Hz（频宽 226 Hz），是典型的伪极点
* 判定：**成立**
* 说明：Praat 的对话框把 5500 Hz 直接标成「= adult female」，手册写成年男性约 5000 Hz、幼童约 8000 Hz。字典原本写「5500 Hz 适合女声或儿童，3000 Hz 适合成年男性」，两个数字都不对。

### 共振峰的数目大约每 1000 Hz 一个，Praat 在 5500 Hz 的范围里预设 5 个

* 来源条目：formant-settings, to-formant-burg
* 实测值：要求 5 个共振峰时 Praat 在 0.4 秒处给出 4 个：F1, F2, F3, F4；Praat 每个共振峰用两个极点，所以 5 个共振峰是 10 个极点
* 判定：**成立**
* 说明：Praat 每个共振峰用两个极点，所以 5 个共振峰是 10 个极点；「每 1000 Hz 一个」说的是共振峰，不是极点。字典原本写「极点数目每 1000 Hz 一个，所以 5500 Hz 需要 5 到 6 个」，前后不一致。

### 共振峰必须在奈奎斯特上限之下才谈得上有意义

* 来源条目：concept-formant, to-formant-burg, formant-settings
* 实测值：奈奎斯特上限 8000 Hz；实测 F1=695 Hz, F2=1065 Hz, F3=1206 Hz, F4=4080 Hz
* 判定：**成立**
* 说明：这个样音的 F1、F2、F3 都在 8000 Hz 以下；Praat 的做法是把上限设成采样率的两倍来分析，再把超出的部分切掉。

### 字典对 F1/F2 没有写数值范围，只说明 F1 对应口腔开度、F2 对应舌位

* 来源条目：concept-formant, formant-object
* 实测值：F1=695 Hz，F2=1065 Hz，F3=1206 Hz；字典没有写 F1/F2 的数值范围，只说 F1 与口腔开度有关、F2 与舌位有关
* 判定：**成立**
* 说明：量到的 F1 与 F2 落在一般元音的常见范围里，所以这一条没有可以被推翻的数值主张。

### To Intensity... 对话框的预设最低基频是 100 Hz

* 来源条目：ow-to-intensity, workflow-intensity, type-intensity
* 实测值：Parselmouth 介面默认值 minimum_pitch = 100.0（对应 Praat 对话框里的 Pitch floor (Hz)）
* 判定：**成立**
* 说明：75 Hz 是 To Pitch... 的预设下限；To Intensity... 的预设是 100 Hz。字典好几个条目都写「预设最低基频（75 Hz）」。

### 最低基频设得比说话者的基频还高时，强度曲线才会出现音高周期的波纹

* 来源条目：ow-to-intensity, workflow-intensity, type-intensity
* 实测值：下限 75 Hz 时峰峰值 0.0032 dB；下限 100 Hz 时峰峰值 0.0069 dB；下限 300 Hz 时峰峰值 0.1837 dB；下限 400 Hz 时峰峰值 0.3526 dB。参考：Praat 手册说下限设太高会出现音高同步的强度起伏，设太低则曲线被抹平
* 判定：**成立**
* 说明：波纹是下限设得太高造成的，不是预设太低造成的；Praat 手册的说法是「设太高会出现音高同步的起伏，设太低则曲线被抹平」。

## 4. 字典里提到数字、但这次没有自动核对的条目

下面这些条目同样提到可量测的量。有勾的是这次已经用 Parselmouth 重算过的条目，没有勾的是目前只有教科书或 Praat 手册当依据、还没有自动量测的条目（多半是界面上的小细节，例如按键组合或标签文字）。

| 量 | 提到它的条目 |
| --- | --- |
| 75 Hz | [x] ow-analyse-periodicity, [x] workflow-pitch |
| 600 Hz | [x] ow-analyse-periodicity, [x] to-pitch, [x] pitch-settings, [ ] canvas-pitch, [x] workflow-pitch |
| 100 Hz | [x] ow-to-intensity, [ ] intensity-menu, [x] workflow-intensity |
| Nyquist | [ ] ow-info, [x] ow-convert, [ ] sound-object, [x] get-sampling-frequency, [ ] spectrogram-view-range, [ ] workflow-convert, [ ] concept-sound-file-formats, [x] concept-sampling-frequency, [x] concept-nyquist-limit |
| window length | [ ] ow-info, [x] ow-analyse-spectrum, [ ] objects-menu-new, [ ] spectrogram-object, [x] to-spectrogram, [ ] new-menu-sound, [ ] spectrogram-settings, [x] spectrogram-window-length, [ ] zoom-in, [ ] canvas-spectrogram, [ ] type-spectrogram |
| 1.3 / window | [x] ow-analyse-spectrum, [x] to-spectrogram, [x] spectrogram-window-length |
| formant ceiling | [x] to-formant-burg, [ ] spectrogram-view-range, [x] formant-settings, [ ] picture-logarithmic-marks, [x] workflow-formant, [x] concept-formant |
| dB reference | [x] ow-to-intensity, [x] intensity-object, [x] get-intensity-db, [x] get-intensity, [x] workflow-intensity, [x] type-intensity |

## 5. 图怎么接到 hover 卡片上

卡片其实已经会显示 Praat 绘图区的截图，那是最贴近学生当下操作的东西；Parselmouth 做的图是离线替代方案，永远不碰正在运行的 Praat，所以适合两种场合：一是 Praat 没开、或者学生的机器上没有 Praat 的时候，卡片改用 `praatao/figures.py` 预先算好的 PNG；二是要讲某个分析本身（例如 0.025 秒的窗长约合 52 Hz 的解析度），图比截图更能把话讲清楚。接法很简单：`praatao.figures.available_figures()` 列出已经画好的图种，`praatao.figures.figure_path(kind)` 给出该图的路径，卡片在需要图的时候把那个路径交给现有的图片显示逻辑，拿不到就照旧用截图。本次没有动介面，只是把图、模组与这个说明准备好。

## 6. 复现

```
python tools\parselmouth_check.py     # 核对并重写本文件
python -m praatao.figures              # 重新产生五张图
```
