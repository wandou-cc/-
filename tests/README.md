# 测试文件夹

本文件夹包含所有测试脚本和测试数据。

## 测试文件

### test_cci_real_data.py
使用真实BTC K线数据测试CCI指标

**功能**：
- 读取K.json中的真实K线数据
- 计算CCI指标
- 显示详细的CCI值和统计信息
- 检测买入/卖出信号
- 分析当前市场状态

**运行方法**：
```bash
cd tests
python test_cci_real_data.py
```

或从根目录运行：
```bash
python tests/test_cci_real_data.py
```

## 测试数据

### K.json
真实的BTC K线数据（JSON格式）

**数据格式**：
```json
{
    "code": "0",
    "msg": "",
    "data": [
        [时间戳, 开盘价, 最高价, 最低价, 收盘价, 其他]
    ]
}
```

## 添加新的测试

创建新的测试文件时，请确保：

1. 正确导入指标模块：
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from indicators.your_indicator import YourIndicator
```

2. 使用相对路径读取测试数据：
```python
data_path = os.path.join(os.path.dirname(__file__), 'K.json')
```

3. 包含完整的测试文档和说明

## 测试建议

- 测试批量计算和增量更新的一致性
- 测试边界条件（数据不足、数据异常等）
- 验证与TradingView的计算结果一致性
- 测试交易信号的准确性

