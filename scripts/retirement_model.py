import pandas as pd
import numpy as np

# 读取原始数据
file_path = 'qd1.xlsx'
data = pd.read_excel(file_path)

# 提取基础数据，适应表格中的格式
# 假设表格中包含列：'车型', '品牌', '能源', '级别', '价格', '电池供应商', '电芯品牌', '电池类型', '电池电量', '电机类型', '时间', '销量'
data = data.rename(columns={
    '车型': 'Car_Model',
    '品牌': 'Brand',
    '能源': 'Energy_Type',
    '级别': 'Category',
    '价格': 'Price',
    '电池供应商': 'Battery_Supplier',
    '电芯品牌': 'Cell_Brand',
    '电池类型': 'Battery_Type',
    '电池电量': 'Battery_Capacity',
    '电机类型': 'Motor_Type',
    '时间': 'Date',
    '销量': 'Monthly_Sales'
})

# 提取时间信息
# 假设 'Date' 列格式为 'YYYY-MM'
data['Year'] = pd.to_datetime(data['Date']).dt.year
data['Month'] = pd.to_datetime(data['Date']).dt.month

# 确保数据格式正确
required_columns = ['Brand', 'Year', 'Month', 'Monthly_Sales']
for col in required_columns:
    if col not in data.columns:
        raise ValueError(f"缺少必要的列: {col}")

data['Monthly_Sales'] = data['Monthly_Sales'].astype(float)

# Step 1: 国家规划的未来销量预测
# 根据国家规划趋势，计算每年总销量和电动车销量占比
def predict_city_sales(base_data, start_year, end_year):
    years = list(range(start_year, end_year + 1))
    total_sales = {
        2020: 30_000_000,
        2025: 35_000_000,
        2030: 38_000_000
    }
    ev_ratios = {
        2020: 0.07,
        2025: 0.15,
        2030: 0.40
    }

    # 线性插值每年的总销量和电动车占比
    total_sales_trend = np.interp(years, list(total_sales.keys()), list(total_sales.values()))
    ev_ratio_trend = np.interp(years, list(ev_ratios.keys()), list(ev_ratios.values()))

    # 假设该城市的销量是全国销量的一个固定比例
    city_ratio = base_data['Monthly_Sales'].sum() / (30_000_000 * 12)  # 基于2020年的数据估算比例

    # 预测每年的城市销量和电动车销量
    city_sales = total_sales_trend * city_ratio
    ev_sales = city_sales * ev_ratio_trend

    # 分解到每个月
    monthly_sales = []
    for year, ev_sale in zip(years, ev_sales):
        for month in range(1, 13):
            monthly_sales.append({'Year': year, 'Month': month, 'EV_Sales': ev_sale / 12})

    return pd.DataFrame(monthly_sales)

# Step 2: 使用威布尔分布计算退役概率
def weibull_cdf(l, lambda_, k):
    return 1 - np.exp(-(l / lambda_) ** k)

# Step 3: 根据斯坦福模型计算退役量
def calculate_retired_batteries(sales_data, lambda_, k):
    retired_batteries = []
    for index, row in sales_data.iterrows():
        year, month, sales = row['Year'], row['Month'], row['EV_Sales']
        current_time = (year - sales_data['Year'].min()) * 12 + month

        total_retired = 0
        for past_index, past_row in sales_data.iterrows():
            past_time = (past_row['Year'] - sales_data['Year'].min()) * 12 + past_row['Month']
            if past_time >= current_time:
                break

            # 销量乘以威布尔分布的退役概率
            l = current_time - past_time
            p_retired = weibull_cdf(l, lambda_, k)
            total_retired += past_row['EV_Sales'] * p_retired

        retired_batteries.append({'Brand': row['Brand'] if 'Brand' in row else 'Unknown',
                                  'Year': year,
                                  'Month': month,
                                  'Retired_Batteries': total_retired})

    return pd.DataFrame(retired_batteries)

# 预测未来销量
predicted_sales = predict_city_sales(data, 2025, 2035)

# 计算退役量
lambda_param = 60
k_param = 3.5
retired_batteries = calculate_retired_batteries(predicted_sales, lambda_param, k_param)

# 保存结果
retired_batteries.to_csv('predicted_retired_batteries.csv', index=False)
