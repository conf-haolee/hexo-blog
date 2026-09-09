---
title: HALCON 入门培训：从基础图像处理到 2D 定位与 AOI 全流程实战
date: 2026-08-31
permalink: /2026/08/31/halcon-2d-aoi/
tags:
- halcon
- 2D定位
- AOI
categories:
- [工作, 机器视觉]
---

<div align="center">
<img src=https://raw.githubusercontent.com/conf-haolee/Images/master/PicGoImg20260901093409966.png  width=400px />
</div>

> 本文整理自一次面向客户现场的 HALCON 入门培训，目标不是堆砌算子，而是帮助初学者建立一套完整的工业视觉思路：**图像获取 → 基础处理 → 2D 定位 → ROI 跟随 → AOI 检测 → OK/NG 判定**。
>
> 适合人群：刚接触 HALCON 的视觉工程师、设备工程师、自动化工程师，以及希望快速理解传统 2D AOI 项目整体流程的开发人员。

---

<!--more-->

## 1. 培训目标

HALCON 的算子很多，但真正进入工业现场后，常用流程其实比较固定。相比“记算子”，更重要的是建立算法流程意识。

这次培训主要围绕以下几个目标展开：

- 熟悉 HDevelop 的基本使用方式
- 理解 Image、Region、XLD 三类核心对象
- 掌握阈值、连通域、形态学、特征筛选等基础处理方法
- 掌握基于 Shape Model 的 2D 定位方法
- 理解定位后如何实现 ROI 跟随
- 掌握几类常见 AOI 检测思路
- 跑通一个完整的“定位 + 检测 + 判定”项目流程

最终希望学员能够看懂如下流程：

```text
图像获取
   ↓
产品定位
   ↓
坐标变换
   ↓
ROI 跟随
   ↓
缺陷 / 尺寸 / 有无检测
   ↓
OK / NG
```

---

## 2. HDevelop 入门：先学会调试，再学算子

初学 HALCON 时，建议优先熟悉 HDevelop，而不是一开始就背大量算子。

常用窗口主要包括：

- Program Window：程序编辑区
- Graphics Window：图像与区域显示窗口
- Variable Window：变量查看窗口
- Operator Window：算子调用窗口
- Procedure：过程封装与复用
- Example Browser：官方示例浏览器
- Operator Reference：算子帮助文档

一个非常重要的学习方法是：

> 不需要记住所有算子，但一定要学会搜索算子、查看帮助和参考官方例程。

例如：

```text
阈值分割        threshold
连通域          connection
区域筛选        select_shape
模板匹配        find_shape_model
尺寸测量        measure / metrology
表面缺陷        dyn_threshold / variation_model
二维码          data code
条码            barcode
```

HALCON 自带的 Example Browser 是非常有价值的学习资源。很多实际项目都可以先从官方例程中找到接近的思路，再根据现场需求修改。

---

## 3. HALCON 三类核心对象：Image、Region、XLD

理解这三类对象，是理解 HALCON 的基础。

### 3.1 Image：图像

Image 保存真实像素数据，例如：

```halcon
read_image (Image, 'test.png')
```

常见操作包括：

```text
read_image
rgb1_to_gray
mean_image
gauss_filter
median_image
```

Image 适合进行灰度处理、滤波、图像增强等操作。

---

### 3.2 Region：区域

Region 是二值区域，可以理解为图像中“哪些像素属于目标”。

例如：

```halcon
threshold (Image, Region, 0, 120)
```

常见 Region 操作：

```text
threshold
connection
select_shape
opening_circle
closing_circle
fill_up
union1
intersection
difference
```

在传统 AOI 中，Region 使用频率非常高。

---

### 3.3 XLD：亚像素轮廓

XLD 常用于高精度轮廓、直线、圆弧和边缘分析。

例如：

```halcon
edges_sub_pix (Image, Edges, 'canny', 1, 20, 40)
```

XLD 更适合：

- 亚像素边缘提取
- 直线拟合
- 圆弧拟合
- 轮廓匹配
- 精密测量

简单理解：

```text
Image  → 像素数据
Region → 区域数据
XLD    → 亚像素轮廓数据
```

---

## 4. HALCON 基础图像处理流程

一个非常典型的基础 Region 流程是：

```text
Image
 ↓
Threshold
 ↓
Morphology
 ↓
Connection
 ↓
Select Shape
 ↓
Result
```

对应代码可以写成：

```halcon
read_image (Image, 'part.png')

threshold (Image, Region, 0, 120)

connection (Region, ConnectedRegions)

select_shape (ConnectedRegions, SelectedRegions, 'area', 'and', 1000, 999999)

area_center (SelectedRegions, Area, Row, Column)
```

几个非常常用的算子：

```text
threshold
connection
select_shape
area_center
```

在工业视觉中，这套组合常用于：

- 产品有无检测
- 孔洞数量统计
- 缺料检测
- 元件数量检测
- 大面积污渍检测
- 产品轮廓提取

---

## 5. 形态学处理：让 Region 更稳定

阈值分割后的区域通常不是最终结果，还需要通过形态学处理去掉噪点或填补小缺口。

常见算子：

```halcon
opening_circle
closing_circle
fill_up
erosion_circle
dilation_circle
```

### opening_circle

主要用途：

- 去除小噪点
- 去除细小连接

### closing_circle

主要用途：

- 填补小缺口
- 连接靠得很近的区域

### fill_up

用于填充 Region 内部孔洞。

在培训中建议让客户直接观察形态学处理前后的 Region 变化，这比单纯讲概念更容易理解。

---

# 6. 2D 定位：Shape-Based Matching

在工业视觉中，产品通常不会每次都出现在完全相同的位置。

可能存在：

- X 方向偏移
- Y 方向偏移
- 旋转
- 一定程度的遮挡
- 灰度变化

因此在 AOI 检测前，一般需要先定位产品。

HALCON 最经典的 2D 定位方法之一就是：

```halcon
create_shape_model
find_shape_model
```

---

## 6.1 Shape Model 建模流程

基本流程：

```text
模板图片
   ↓
选择模板 ROI
   ↓
reduce_domain
   ↓
create_shape_model
   ↓
得到 ModelID
```

示例：

```halcon
read_image (ModelImage, 'model.png')

gen_rectangle1 (ROI, 100, 100, 400, 500)

reduce_domain (ModelImage, ROI, ImageReduced)

create_shape_model (ImageReduced, 'auto', rad(-20), rad(40), 'auto', 'auto', 'use_polarity', 'auto', 'auto', ModelID)
```

---

## 6.2 Shape Model 匹配

运行时：

```halcon
find_shape_model (Image, ModelID, rad(-20), rad(40), 0.5, 1, 0.5, 'least_squares', 0, 0.9, Row, Column, Angle, Score)
```

常用返回值：

```text
Row
Column
Angle
Score
```

这四个参数基本可以理解为：

```text
产品中心位置 X / Y
产品旋转角度
匹配得分
```

---

## 6.3 Shape Model 常见参数

### MinScore

表示最低允许匹配分数。

例如：

```text
0.8
```

通常要求较严格。

如果设置为：

```text
0.3
```

则更容易匹配到目标，但误匹配风险也会增加。

因此 MinScore 不是越低越好，而是需要根据现场样本进行验证。

### NumMatches

表示最多查找多少个目标。

### MaxOverlap

用于多目标场景，控制匹配结果之间允许的重叠程度。

### SubPixel

控制亚像素定位精度。

### Greediness

影响匹配速度和搜索完整性。

---

# 7. 定位之后真正关键的一步：ROI 跟随

初学者经常会问：

> 模板已经找到产品了，然后接下来怎么做？

真正的 AOI 项目中，Shape Model 的价值不是只得到一个中心坐标，而是建立一个统一的产品坐标系。

整体思路：

```text
模板参考坐标
     ↓
产品实际坐标
     ↓
计算刚性变换矩阵
     ↓
所有检测 ROI 跟随产品变换
```

HALCON 中常用：

```halcon
vector_angle_to_rigid
affine_trans_region
```

---

## 7.1 建立仿射矩阵

假设模板参考位置：

```halcon
RefRow := 500
RefCol := 800
RefAngle := 0
```

实际定位结果：

```text
Row
Column
Angle
```

计算变换矩阵：

```halcon
vector_angle_to_rigid (RefRow, RefCol, RefAngle, Row, Column, Angle, HomMat2D)
```

---

## 7.2 让检测 ROI 跟随产品运动

模板坐标下提前画好 AOI ROI：

```halcon
gen_rectangle1 (InspectionROI, 300, 300, 500, 500)
```

运行时变换：

```halcon
affine_trans_region (InspectionROI, InspectionROITrans, HomMat2D, 'nearest_neighbor')
```

于是即使产品发生：

```text
左移
右移
上移
下移
旋转
```

检测 ROI 仍然可以跟随产品运动。

这是传统 2D AOI 中非常重要的一种工程思想。

---

# 8. AOI 检测一：有无 / 缺料 / 多料检测

这是非常适合入门的 AOI 类型。

假设产品上正常应该有 4 个孔，可以采用：

```halcon
reduce_domain (Image, CheckROI, ImageReduced)

threshold (ImageReduced, Region, 0, 80)

connection (Region, ConnectedRegions)

select_shape (ConnectedRegions, Holes, 'area', 'and', 500, 3000)

count_obj (Holes, Number)

if (Number = 4)
    Result := 'OK'
else
    Result := 'NG'
endif
```

这种流程非常适合：

- 孔数量检测
- PIN 脚有无检测
- 螺丝有无检测
- 装配件缺失检测
- 零件数量检测

核心思想不是“检测一个像素”，而是把符合目标特征的 Region 提取出来，再进行数量和特征判断。

---

# 9. AOI 检测二：脏污、划伤和局部灰度异常

如果背景灰度比较均匀，而缺陷表现为局部变暗或变亮，可以使用动态阈值。

典型流程：

```halcon
mean_image (Image, ImageMean, 25, 25)

dyn_threshold (Image, ImageMean, DefectRegion, 15, 'dark')

connection (DefectRegion, ConnectedRegions)

select_shape (ConnectedRegions, SelectedDefects, 'area', 'and', 20, 999999)
```

与普通 threshold 相比：

```text
threshold
→ 使用固定灰度阈值
```

而：

```text
dyn_threshold
→ 当前像素与局部背景进行比较
```

因此 dyn_threshold 对光照缓慢变化、产品表面灰度不完全一致的场景通常更有适应性。

常见应用：

- 脏污
- 黑点
- 白点
- 划伤
- 局部亮斑
- 表面异物

当然，真实 AOI 项目中还需要结合：

```text
缺陷面积
缺陷长度
缺陷位置
缺陷数量
缺陷灰度差
```

来最终判定 OK / NG。

---

# 10. AOI 检测三：尺寸检测

尺寸检测和简单 Region 检测的思路略有不同。

比较常见的 HALCON 测量体系包括：

```text
Measure
Metrology
```

---

## 10.1 Measure 测量

常见算子：

```halcon
gen_measure_rectangle2
measure_pos
measure_pairs
```

基本思路：

```text
建立测量矩形
      ↓
沿指定方向搜索灰度边缘
      ↓
找到边缘位置
      ↓
计算距离
```

适合：

- 宽度检测
- 高度检测
- 间距检测
- 边缘位置检测

---

## 10.2 Metrology Model

如果需要拟合：

- 直线
- 圆
- 椭圆
- 矩形

可以使用 Metrology Model。

典型算子：

```halcon
create_metrology_model
add_metrology_object_line_measure
add_metrology_object_circle_measure
apply_metrology_model
```

简单理解：

```text
简单局部边缘尺寸 → Measure

完整几何元素拟合 → Metrology
```

---

# 11. 一个完整 AOI 项目应该如何组织

培训过程中最值得强调的，不是某一个单独算子，而是完整工程流程。

假设现在有一个金属零件：

```text
┌───────────────────┐
│   ○           ○   │
│                   │
│      PRODUCT      │
│                   │
│   ○           ○   │
└───────────────────┘
```

需要检测：

1. 产品位置
2. 4 个孔是否完整
3. 中间区域是否存在脏污
4. 某个尺寸是否超差
5. 最终输出 OK / NG

完整流程可以设计成：

```text
Step 1
读取图片

      ↓

Step 2
Shape Model 定位

      ↓

得到
Row / Column / Angle

      ↓

Step 3
vector_angle_to_rigid

      ↓

Step 4
所有检测 ROI 做坐标变换

      ↓

┌─────────────┬─────────────┬─────────────┐
↓             ↓             ↓
孔检测       脏污检测       尺寸检测
↓             ↓             ↓
HoleOK       DirtOK        SizeOK
└─────────────┴─────────────┴─────────────┘
                ↓

Result := HoleOK AND DirtOK AND SizeOK

                ↓

             OK / NG
```

这就是一个最基本的传统 AOI 项目框架。

---

# 12. HALCON AOI 六步法

如果需要给 HALCON 初学者总结一个非常容易记忆的框架，可以概括为：

```text
① 获取图像
     ↓
② 定位产品
     ↓
③ 建立坐标变换
     ↓
④ ROI 跟随
     ↓
⑤ 特征 / 缺陷检测
     ↓
⑥ OK / NG 判定
```

对应 HALCON 常用算子：

```text
read_image / grab_image
        ↓
find_shape_model
        ↓
vector_angle_to_rigid
        ↓
affine_trans_region
        ↓
threshold / dyn_threshold
measure / metrology
        ↓
if / else
        ↓
OK / NG
```

如果理解了这六步，大部分传统 2D AOI 项目都会比较容易继续展开。

---

# 13. 配套的 4 个 HDevelop Demo

这次培训可以配套准备四个由浅入深的 Demo。

## Demo 01：Region 基础处理

文件：

```text
01_HALCON_Basic_Region.hdev
```

重点：

```text
threshold
connection
select_shape
area_center
```

目标：

让学员理解 Image → Region → Connected Region → 特征筛选的基本流程。

---

## Demo 02：Shape Model 2D 定位

文件：

```text
02_ShapeModel_Position.hdev
```

重点：

```text
create_shape_model
find_shape_model
get_shape_model_contours
```

目标：

理解产品存在平移和旋转时如何进行稳定定位。

---

## Demo 03：定位 + ROI 跟随 + AOI

文件：

```text
03_Position_ROI_AOI.hdev
```

重点：

```text
find_shape_model
vector_angle_to_rigid
affine_trans_region
```

目标：

让学员真正理解：

> 模板匹配的最终目的，是建立产品坐标系，让后续 AOI ROI 可以稳定跟随产品。

---

## Demo 04：完整 AOI 流程

文件：

```text
04_Full_AOI_Demo.hdev
```

完整流程：

```text
Image
 ↓
Matching
 ↓
ROI Transform
 ↓
Hole Check
 ↓
Defect Check
 ↓
Measure
 ↓
OK / NG
```

这个 Demo 可以作为整场培训的主线案例。

---

# 14. 推荐学习的 HALCON 官方例程关键词

HALCON 自带大量 Example，很多时候直接搜索关键词比记住某个具体例程名称更方便。

## 基础图像处理

```text
threshold
connection
select_shape
morphology
```

## Shape Matching

```text
shape_model
matching
find_shape_model
```

## Measure

```text
measure
measure_pairs
measure_pos
```

## Metrology

```text
metrology
line
circle
rectangle
```

## AOI / Surface Inspection

```text
surface inspection
defect
dyn_threshold
variation_model
```

## 识别类

```text
data code
barcode
ocr
```

学习 HALCON 一个非常有效的方法就是：

```text
项目问题
   ↓
拆成视觉任务
   ↓
找到对应算子类别
   ↓
查 Operator Reference
   ↓
搜索 Example Browser
   ↓
修改官方 Demo
   ↓
替换为自己的产品图片
```

---

# 15. 工业现场使用 HALCON 时的一些经验

## 15.1 算法稳定性往往首先取决于成像

很多初学者容易陷入不断调阈值、调参数的问题。

实际上工业视觉中经常需要优先检查：

```text
光源
镜头
曝光
产品姿态
背景
反光
景深
相机固定方式
```

如果输入图像本身不稳定，再复杂的算法也很难长期稳定运行。

---

## 15.2 ROI 尽量小

AOI 不需要每次都处理整张图片。

推荐：

```text
全图
 ↓
定位
 ↓
得到产品坐标
 ↓
变换 ROI
 ↓
只处理局部区域
```

优点：

- 计算量更小
- 速度更快
- 干扰更少
- 参数更加稳定

---

## 15.3 不要只看单张图片效果

算法调试完成后，需要建立测试集。

至少覆盖：

```text
正常产品
轻微 NG
严重 NG
位置变化
角度变化
亮度变化
不同批次
极限样本
```

真正的算法稳定性，应当以批量测试结果为准。

---

## 15.4 参数要有工程意义

例如：

```text
MinDefectArea := 20
MaxHoleArea := 3000
MinScore := 0.7
```

最好不要直接把大量数字散落在程序中。

推荐：

- 统一放在程序开头
- 使用有意义的变量名
- 标注参数用途
- 记录调试依据

这样后续维护会轻松很多。

---

# 16. 从 HALCON Demo 到真正工业软件

HDevelop Demo 跑通以后，只是视觉算法开发的第一步。

真正的工业视觉软件通常还包括：

```text
相机触发
   ↓
图像采集
   ↓
HALCON 算法
   ↓
检测结果
   ↓
PLC / TCP / IO
   ↓
设备执行
```

同时还需要：

- 参数管理
- Recipe 管理
- 图像保存
- NG 图记录
- 日志
- 数据统计
- MES 上传
- 异常处理
- 多线程任务
- 相机断线重连

因此 HALCON 的角色更多是：

> 工业视觉软件中的算法引擎。

而不是整个视觉系统本身。

---

# 17. 总结

如果刚开始学习 HALCON，不建议一开始就追求掌握大量复杂算子。

更推荐按照下面的路线学习：

```text
HDevelop 基础
 ↓
Image / Region / XLD
 ↓
Threshold / Connection / Select Shape
 ↓
Shape Model 2D 定位
 ↓
坐标变换与 ROI 跟随
 ↓
基础 AOI
 ↓
Measure / Metrology
 ↓
完整项目
```

其中最重要的几个核心思想是：

1. **先定位，再检测。**
2. **建立产品坐标系，而不是依赖固定像素坐标。**
3. **检测 ROI 尽量局部化。**
4. **阈值、形态学、特征筛选仍然是传统 AOI 的基础。**
5. **算法效果最终必须通过批量样本验证。**
6. **现场稳定性不仅取决于算法，更取决于成像和工程设计。**

对于传统 2D AOI 项目，可以长期记住这条主线：

```text
图像获取
   ↓
定位
   ↓
坐标变换
   ↓
ROI 跟随
   ↓
AOI 检测
   ↓
结果汇总
   ↓
OK / NG
```

理解这条主线之后，再去学习 Shape Model、Measure、Metrology、OCR、Data Code、Deep Learning 等不同模块，就会清晰很多。

---

## 附：培训 Demo 文件建议

```text
HALCON_Training/
│
├─ HALCON入门培训_2D定位与AOI实战博客.md
│
├─ 01_HALCON_Basic_Region.hdev
├─ 02_ShapeModel_Position.hdev
├─ 03_Position_ROI_AOI.hdev
└─ 04_Full_AOI_Demo.hdev
```

后续如果用于公司内部培训，还可以在这套内容基础上继续扩展：

```text
05_Measure_Demo.hdev
06_Metrology_Demo.hdev
07_DataCode_Demo.hdev
08_Image_Acquisition_Demo.hdev
09_DeepLearning_Inference_Demo.hdev
```

逐步形成一套完整的 HALCON 工业视觉培训资料库。
