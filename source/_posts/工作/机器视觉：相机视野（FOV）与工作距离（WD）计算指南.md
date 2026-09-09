---
title: 机器视觉：相机视野（FOV）与工作距离（WD）计算指南
date: 2026-02-10
permalink: /2026/02/10/camera-fov-working-distance/
tags: 
- 机器视觉
- 调试
categories:
- [工作, 机器视觉]
pin: false
plugins:
  - mathjax
---

> 面向视觉工程师的实用笔记：从光学原理 → 工程公式 → 实际项目计算

<!--more-->

在机器视觉项目中，最常见的三个问题：

1. 已知镜头焦距和工作距离，视野有多大？
2. 已知需要的视野，应该留多少工作距离？
3. 当前相机+镜头组合是否合适？

本文用“能落地调试”的方式讲清楚。

------

## 一、基础光学原理

### 1. 薄透镜成像公式

$$
[
\frac{1}{f} = \frac{1}{u} + \frac{1}{v}
]
$$



- **f**：镜头焦距
- **u**：物距（视觉中称为工作距离 WD）
- **v**：像距（传感器到镜头主点的距离）

### 2. 放大倍率 β

$$
\beta = \frac{v}{u} = \frac{\text{像尺寸}}{\text{物尺寸}}
$$

在视觉里：

- 物尺寸 → 视野 FOV
- 像尺寸 → 传感器尺寸

所以：
$$
\beta = \frac{Sensor}{FOV}
$$

### 3. 工程推导

由：
$$
WD = f \cdot \frac{1+\beta}{\beta}
$$
代入 β = Sensor / FOV，可得最常用公式：
$$
FOV = Sensor \times \frac{WD - f}{f}
$$

> 这就是调机时最核心的计算式

------

## 二、工程中的关键概念

### 1. 传感器尺寸怎么来？

$$
Sensor宽 = 分辨率
$$

$$
_{H} \times 像元尺寸
]
[
Sensor高 = 分辨率_{V} \times 像元尺寸
$$



### 2. 单像素精度

$$
精度 = \frac{FOV}{分辨率}
$$

### 3. 注意点

- WD 指的是“到镜头主点”的距离
- 实际量的是到镜头前端，会有几毫米偏差
- 近距离对焦时有效焦距会轻微漂移

------

## 三、实例计算（真实设备）

### 1. 相机参数

- 型号：[大恒相机 ME2C-2001-6GM](https://daheng-imaging.com/show-92-1959-1.html)
- 分辨率：5496 × 3672
- 像元：2.4 μm
- 靶面：1"

**计算传感器物理尺寸：**

- 宽：5496 × 2.4μm = 13.19 mm
- 高：3672 × 2.4μm = 8.81 mm

### 2. 镜头参数

- 焦距：16 mm
- 成像圈：1.1"

### 3. 已知条件

- 工作距离 WD = 230 mm

------

### 4. 计算视野

比例因子：
$$
k = \frac{WD - f}{f} = \frac{230 - 16}{16} = 13.375
$$
**水平视野：**
$$
FOV_H = 13.19 \times 13.375 = 176.42\ mm
$$
**垂直视野：**
$$
FOV_V = 8.81 \times 13.375 = 117.87\ mm
$$
**结果：**

- 视野 ≈ **176 × 118 mm**
- 对角 ≈ 212 mm

------

### 5. 单像素精度

$$
176.42 / 5496 = 0.0321 mm/px
$$

> 约 32 μm/像素

------

## 四、换不同焦距（12mm / 25mm）对比（同 WD=230mm）

> 假设相机不变（IMX183，Sensor=13.19×8.81mm），工作距离 WD=230mm 不变，只更换焦距。

统一公式：
$$
FOV = Sensor imes rac{WD - f}{f}
$$

### 1) 换成 12mm 镜头

$$
k = rac{230-12}{12} = 18.1667
$$

- 水平视野：FOV_H = 13.19 × 18.1667 ≈ **239.63 mm**
- 垂直视野：FOV_V = 8.81 × 18.1667 ≈ **160.10 mm**
- 单像素精度：239.63 / 5496 ≈ **0.0436 mm/px**（约 43.6 μm/px）

### 2) 换成 25mm 镜头

$$
k = rac{230-25}{25} = 8.2
$$

- 水平视野：FOV_H = 13.19 × 8.2 ≈ **108.16 mm**
- 垂直视野：FOV_V = 8.81 × 8.2 ≈ **72.26 mm**
- 单像素精度：108.16 / 5496 ≈ **0.0197 mm/px**（约 19.7 μm/px）

### 3) 一眼看懂的结论

- **焦距越短（12mm）→ 视野更大、单像素对应更大（精度更粗），更适合“看全/定位/读码”。**
- **焦距越长（25mm）→ 视野更小、单像素对应更小（精度更细），更适合“测量/细小缺陷”。**

把三种焦距放一起（WD=230mm）：

| 焦距 | 水平视野 (mm) | 垂直视野 (mm) | 单像素精度 (mm/px) |
| ---- | ------------- | ------------- | ------------------ |
| 12mm | 239.63        | 160.10        | 0.0436             |
| 16mm | 176.42        | 117.87        | 0.0321             |
| 25mm | 108.16        | 72.26         | 0.0197             |

> 备注：表格为近似值。实际还会受“对焦位置/主点定义/有效焦距漂移”等影响，建议最终用标定板实测校正。

------

## 四、反推应用

### 1. 若目标视野 200 mm

需要：
$$
WD = f \cdot \frac{FOV + Sensor}{Sensor}
$$

### 2. 是否合适判断

- 若需要 10 μm 精度 → 该方案不够
- 若读码/定位 → 完全可用

------

## 五、工程经验

1. 实测与计算差异 3~5%
2. WD 定义要统一
3. 高精度项目必须做标定
4. 近距离注意景深

------

## 六、Python 快速计算小脚本（现场调机版）

下面脚本直接输入：分辨率、像元尺寸、焦距、工作距离，就能输出 **Sensor 尺寸、视野、单像素精度**。

```python
from dataclasses import dataclass


@dataclass
class Camera:
    res_h: int          # 水平分辨率 (px)
    res_v: int          # 垂直分辨率 (px)
    pixel_um: float     # 像元尺寸 (μm)


def calc_sensor_mm(cam: Camera) -> tuple[float, float]:
    """返回传感器宽高 (mm)"""
    sensor_w = cam.res_h * cam.pixel_um / 1000.0
    sensor_h = cam.res_v * cam.pixel_um / 1000.0
    return sensor_w, sensor_h


def calc_fov_mm(cam: Camera, f_mm: float, wd_mm: float) -> dict:
    """已知焦距 f(mm) 与工作距离 WD(mm)，计算 FOV 与单像素精度"""
    if f_mm <= 0:
        raise ValueError("f_mm must be > 0")
    if wd_mm <= f_mm:
        raise ValueError("wd_mm must be greater than f_mm (otherwise k becomes <= 0)")

    sensor_w, sensor_h = calc_sensor_mm(cam)

    k = (wd_mm - f_mm) / f_mm
    fov_w = sensor_w * k
    fov_h = sensor_h * k

    mm_per_px_h = fov_w / cam.res_h
    mm_per_px_v = fov_h / cam.res_v

    return {
        "sensor_w_mm": sensor_w,
        "sensor_h_mm": sensor_h,
        "k": k,
        "fov_w_mm": fov_w,
        "fov_h_mm": fov_h,
        "mm_per_px_h": mm_per_px_h,
        "mm_per_px_v": mm_per_px_v,
    }


if __name__ == "__main__":
    # 你的相机：ME2C-2001-6GM / IMX183
    cam = Camera(res_h=5496, res_v=3672, pixel_um=2.4)

    wd = 230.0
    for f in (12.0, 16.0, 25.0):
        r = calc_fov_mm(cam, f_mm=f, wd_mm=wd)
        print(f"
=== f={f:.1f}mm, WD={wd:.1f}mm ===")
        print(f"Sensor: {r['sensor_w_mm']:.3f} x {r['sensor_h_mm']:.3f} mm")
        print(f"FOV:    {r['fov_w_mm']:.2f} x {r['fov_h_mm']:.2f} mm")
        print(f"Res:    {r['mm_per_px_h'] * 1000:.1f} um/px (H)")
```

你在现场只要改这几项就行：

- `res_h/res_v/pixel_um`（相机）
- `wd`（你的工作距离）
- `for f in (...)`（你要对比的镜头焦距）

------

## 七、快速计算步骤

1. 算传感器尺寸
2. 代入 FOV 公式
3. 计算像素精度
4. 评估任务可行性

------

## 七、结论

对于本套设备：

- WD=230mm
- 16mm 镜头
- 1" 2000万相机

> 可得到约 176×118mm 视野，32μm/px 的成像能力。

适合：

- 读码
- 外观检测
- 中等精度测量

不适合：

- <0.02mm 的高精度尺寸测量

------

> 本文可直接作为现场调机计算模板

