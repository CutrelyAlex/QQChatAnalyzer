from re import I
from src.LineProcess import *
from src.CutWords import *
from src.WordCloudMaker import *
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
from collections import defaultdict, Counter
from src.LineProcess import process_lines_data
import jieba
import json


def print_user_message_ranking(all_linesData):
    user_counter = Counter()
    user_name_map = {}
    for data in all_linesData:
        user_counter[data.qq] += 1
        user_name_map[data.qq] = data.sender
    print("User message ranking (Top 10):")
    for qq, count in user_counter.most_common(10):
        print(f"{user_name_map[qq]}({qq}): {count} messages")


def CIYUN_SETUP():
    mode = input("输入模式 全员/部分人 (all/part): ").strip().lower()
    file_name = input("输入文本文件名(如 1.txt): ").strip()
    part_name_input = input("输入QQ号，用逗号分开:").strip()
    
    if(',' in part_name_input):
        part_name = [name.strip() for name in part_name_input.split(',')] if part_name_input else None
    else:
        part_name = [part_name_input]
        
    print("输入的部分人QQ号: " + str(part_name))
    lines_to_process = process_lines(file_name, mode, part_name)

    
    print("待处理文本预览(99条):" + str(lines_to_process[0:99]))
    print("-"*25)
    print("行数:" + str(len(lines_to_process)))

    word_counts,words_top = cut_words(lines_to_process, 50)
    print(words_top)
    make_cloude(word_counts)

def get_top_speakers_by_period(all_linesData, period_hours=3):
    periods = 24 // period_hours
    period_user_counts = [defaultdict(int) for _ in range(periods)]  # key: qq, value: count
    period_user_name = [defaultdict(str) for _ in range(periods)]    # key: qq, value: sender

    for data in all_linesData:
        if not data.timepat:
            continue
        hour = int(data.get_time().split(":")[0])
        period = hour // period_hours
        period_user_counts[period][data.qq] += 1
        period_user_name[period][data.qq] = data.sender

    result = []
    for i, user_count in enumerate(period_user_counts):
        if user_count:
            top_qq, top_count = Counter(user_count).most_common(1)[0]
            top_sender = period_user_name[i][top_qq]
            result.append((i*period_hours, (i+1)*period_hours-1, top_sender, top_qq, top_count))
        else:
            result.append((i*period_hours, (i+1)*period_hours-1, None, None, 0))
    return result


def analyze_and_plot_bins(bin_minutes=2):
    file_name = "1.txt"
    mode = "all"
    part_name = None

    all_lines, all_linesData = process_lines_data(file_name, mode, part_name)

    bins_per_hour = 60 // bin_minutes
    total_bins = 24 * bins_per_hour
    bin_counts = [0] * total_bins
    hour_counts = [0] * 24

    for data in all_linesData:
        if not data.timepat:
            continue
        h, m, _ = map(int, data.get_time().split(":"))
        bin_index = h * bins_per_hour + m // bin_minutes
        bin_counts[bin_index] += 1
        hour_counts[h] += 1

    # 输出每小时的发言数
    print("Message count per hour:")
    for hour in range(24):
        print(f"{hour:02d}:00~{hour:02d}:59 - {hour_counts[hour]} messages")

    # 画密集散点图
    x = list(range(total_bins))
    plt.figure(figsize=(16, 5))
    plt.scatter(x, bin_counts, color='blue', s=8, alpha=0.7)
    plt.xlabel(f"Time ({bin_minutes}-minute bins, 0=00:00, {total_bins-1}=23:{60-bin_minutes:02d})")
    plt.ylabel("Message Count")
    plt.title(f"Message Count by {bin_minutes}-Minute Interval (0~23:59)")
    plt.grid(True, linestyle='--', alpha=0.3)
    # 设置x轴刻度为每小时一个
    plt.xticks([i * bins_per_hour for i in range(25)], [f"{i:02d}:00" for i in range(25)], rotation=45)
    plt.tight_layout()
    plt.show()


def plot_weekhour_heatmap(all_linesData):
    # 7天×24小时的矩阵
    heatmap = np.zeros((7, 24), dtype=int)
    all_dates = set()
    for data in all_linesData:
        if not data.timepat:
            continue
        try:
            dt = datetime.strptime(data.timepat, "%Y-%m-%d %H:%M:%S")
            weekday = dt.weekday()  # 0=Monday, 6=Sunday
            hour = dt.hour
            heatmap[weekday, hour] += 1
            all_dates.add(dt.date())
        except Exception:
            continue

    heatmap_list = heatmap.tolist()

    # 每天的总消息数与平均每小时消息数
    daily_total = [int(np.sum(heatmap[day])) for day in range(7)]
    daily_avg_per_hour = [round(np.mean(heatmap[day]), 2) for day in range(7)]

    # 每小时（跨天）的总消息数与平均每天该小时消息数
    hourly_total = [int(np.sum(heatmap[:, hour])) for hour in range(24)]
    hourly_avg_per_day = [round(np.mean(heatmap[:, hour]), 2) for hour in range(24)]

    # 总消息数、总天数
    total_messages = int(np.sum(heatmap))
    total_days = len(all_dates)

    # 输出适合AI分析的结构
    result = {
        "heatmap": heatmap_list,
        "daily_total": daily_total,
        "daily_avg_per_hour": daily_avg_per_hour,
        "hourly_total": hourly_total,
        "hourly_avg_per_day": hourly_avg_per_day,
        "total_messages": total_messages,
        "total_days": total_days
    }
    print("7*24小时消息分布及辅助参数（适合AI分析结构，0=Monday）：")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    plt.figure(figsize=(12, 4))
    plt.imshow(heatmap, aspect='auto', cmap='YlOrRd')
    plt.colorbar(label='Message Count')
    plt.xlabel('Hour of Day')
    plt.ylabel('Day of Week')
    plt.title('Message Density Heatmap (Weekday vs Hour)')
    plt.xticks(range(24), [f"{h:02d}" for h in range(24)])
    plt.yticks(range(7), ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    plt.tight_layout()
    plt.show()

def plot_qq_length_distribution(all_linesData):
    from collections import Counter, defaultdict

    unique_qq = {}
    for data in all_linesData:
        qq = str(data.qq)
        if qq not in unique_qq:
            unique_qq[qq] = data.sender  # 保留一个示例 sender

    qq_length_counter = Counter()
    qq_examples = defaultdict(set)

    for qq, sender in unique_qq.items():
        length = len(qq)
        qq_length_counter[length] += 1
        if len(qq_examples[length]) < 5:
            qq_examples[length].add(qq)

    print("各位数QQ号数量分布（去重后）：")
    for length, count in sorted(qq_length_counter.items()):
        examples = ', '.join(list(qq_examples[length]))
        print(f"{length}位: {count} 个（示例: {examples}）")


# 在主程序中调用
if __name__ == "__main__":
    all_lines, all_linesData = process_lines_data("1.txt", "all")
    plot_weekhour_heatmap(all_linesData)

