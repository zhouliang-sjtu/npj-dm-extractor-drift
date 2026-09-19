# 标注表说明与列定义

> **表结构说明**：专家标注直接在  下发的待标注 CSV 中填写。源信息列 + 原文 + A1\_*/A2\_* 双标注列 + flag/note/arbitration。下发时标注列与仲裁列均为空列。

## 列结构（各域通用）

| 列组                | 说明                                           |
| ----------------- | -------------------------------------------- |
| sample\_id / 源信息列 | 编号与溯源（year / exam\_date / pseudo\_id），勿改     |
| text              | 待标注原文（截断长度见抽样脚本）                             |
| A1\_\*            | 标注员 A1 填写（0/1、分级值或数值，规则见《标注手册》）；A1 只填 A1\_ 列 |
| A2\_\*            | 标注员 A2 独立填写（不得参考 A1）；A2 只填 A2\_ 列            |
| flag              | 该份存在规则未覆盖情形时=1                               |
| note              | flag 的原因，一句话（含"左/右/双""息肉大小"等备注）              |
| arbitration       | 仲裁员对 A1≠A2 分歧个案的终版裁定（仅分歧个案由仲裁员填写，标注员留空）      |

各域变量与列数：

| 域（CSV，对应工作簿 sheet）   | 源信息列                                            | 标注变量（A1\_/A2\_ 前缀）                                                                                                                                   | 总列数 |
| -------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | --- |
| ECG\_H               | sample\_id, year, pseudo\_id, text              | ecg\_normal, ecg\_af, ecg\_pac\_pvc, ecg\_stt, ecg\_avblock, ecg\_bbb, ecg\_rate, ecg\_srirr, ecg\_axis, ecg\_qwave\_mi, ecg\_other, ecg\_unreadable | 31  |
| ECHO\_PG             | sample\_id, exam\_date, pseudo\_id, text        | echo\_normal, echo\_variant, echo\_lvh, echo\_la\_dilate, ef\_value, ef\_abnormal, reflux\_grade, echo\_rhythm, echo\_unreadable                     | 25  |
| ABDUS\_PG / ABDUS\_H | sample\_id, exam\_date 或 year, pseudo\_id, text | us\_fatty, us\_fatty\_degree, us\_hepatic\_other, us\_gallstone, us\_kidney\_cyst, us\_unreadable, main\_discrepant                                  | 21  |

## 填写约定

- 二值列填 `1/0`；分级列填 `none/trace_mild/moderate/severe` 或 `轻/中/重`；数值列（ef\_value）填数字
- 空值仅限"该变量不适用"（如echo文本中无EF信息时 ef\_value 留空）
- **先看否定表述再判阳性**（手册通用规则1）
- 每人负责列：A1只填A1\_，A2只填A2\_

## 一致性计算

标注完成并由课题组汇总后，在仓库根目录运行：

```
python code/04_agreement_stats.py --file data/金标准标注工作簿.xlsx --sheet ECHO_PG --cols echo_normal,echo_lvh,echo_la_dilate,ef_abnormal,echo_rhythm
```

分层（年份）一致性自动输出；κ<0.80的变量必须仲裁+手册修订后重标该层。
