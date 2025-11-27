"""
这一步人手动来做，因为带图的题目不多，自动化截图的麻烦大于收益
人：
    - VLM 说带图的，把图给拷上（同级目录，0.png、1.png、...）
    - 简单看一下，反正我也不会高能物理，主要检查：
        - 题目表述正常，从语文上看起来不是个坏题
        - 字段齐全（problem、solution、answer、contributor、image_placeholder、reviewed）
        - 图片处理得当 
    - 看完后在 result.json 中设置一下 reviewed: true
    - Corner cases：
        - 有的答案是“请见文章 arxiv:xxx”，这种先不过审
"""