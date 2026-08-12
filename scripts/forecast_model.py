import pandas as pd
import numpy as np

# Step 1: Load Excel file
file_path = 'forecasted_sales_2025_2035.xlsx'  # 原始文件路径
data = pd.ExcelFile(file_path)
sheet_data = data.parse('Sheet1')

# Step 2: 清理数据并转换时间格式
sheet_data['时间'] = pd.to_datetime(sheet_data['时间'].str.replace('年', '-').str.replace('月', '-1'),
                                    format='%Y-%m-%d')
sheet_data = sheet_data.sort_values(by=['品牌', '时间'])


# Step 3: 定义威布尔分布 CDF 函数
def weibull_cdf(l, lambda_, k):
    """
    Calculate the CDF of the Weibull distribution.

    Parameters:
    l : float
        The time duration.
    lambda_ : float
        The scale parameter of the Weibull distribution.
    k : float
        The shape parameter of the Weibull distribution.

    Returns:
    float
        The CDF value.
    """
    return 1 - np.exp(-(l / lambda_) ** k)


# Step 4: 定义威布尔分布参数
lambda_ = 60  # 电池寿命分布的尺度参数（以月为单位）
k = 3.5  # 电池寿命分布的形状参数

# Step 5: 计算退役电池量
results = []
grouped = sheet_data.groupby('品牌')

for brand, group in grouped:
    group = group.sort_values(by='时间')
    sales = group['销量'].values
    times = group['时间'].values

    # 初始化每月退役电池量
    retirement_volumes = np.zeros_like(sales, dtype=float)

    for i, t in enumerate(times):
        # 对于每个月 t，计算累积退役电池量
        for j, tau in enumerate(times[:i + 1]):  # 考虑所有历史时间
            duration = (t - tau).astype('timedelta64[M]').astype(int)  # 转换为月份差
            retirement_volumes[i] += sales[j] * weibull_cdf(duration, lambda_, k)

    # 存储结果
    for t, rv in zip(times, retirement_volumes):
        results.append({'品牌': brand, '时间': t, '退役电池量': rv})

# 转换结果为 DataFrame
retirement_data = pd.DataFrame(results)

# Step 6: 保存结果到文件
output_path = '退役电池量预测结果.xlsx'
retirement_data.to_excel(output_path, index=False)

print(f"预测结果已保存到: {output_path}")
