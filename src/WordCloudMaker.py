from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator
import matplotlib.pyplot as plt

def make_cloude(word_counts, var_max_words=2000):
	## 制作词云
    backgroud_Image = plt.imread('mask.png')  #选择背景图片，图片要与.py文件同一目录
    print('加载背景图片成功！')

    ## 设置词云样式  
    wc = WordCloud(  
        background_color='white',   # 设置背景颜色  
        mask=backgroud_Image,       # 设置背景图片  
        font_path='C:\Windows\Fonts\SIMHEI.ttf',
        max_words=var_max_words,     # 设置最大词数 
        stopwords=STOPWORDS,        
        max_font_size=150,  # 设置字体最大值  
        random_state=30,    
        width=1960,          # 设置图片宽度
        height=1080          # 设置图片高度
    )

    wc.generate_from_frequencies(word_counts)  #通过频率生成词云
    print('开始加载文本')  

    img_colors = ImageColorGenerator(backgroud_Image)  

    wc.recolor(color_func=img_colors) 

    plt.imshow(wc)  # 显示词云图
    plt.axis('off') # 是否显示x轴、y轴下标  
    plt.show()
    print('生成词云成功！')