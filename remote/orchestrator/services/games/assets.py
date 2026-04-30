from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Riddle:
    """Riddle data structure."""
    question: str
    answer: str
    aliases: list[str]
    hint: str


# Riddle assets - 8 riddles with varying difficulty
RIDDLES: list[Riddle] = [
    Riddle(
        question="有个老爷爷，胡须白又长。每天都来剪，但永远剪不完。你知道他是谁吗？",
        answer="月亮",
        aliases=["月亮", "月", "明月"],
        hint="每个月都会圆缺，还能在天空照亮大地。",
    ),
    Riddle(
        question="小小的东西，却能在黑夜里照亮房间。你猜是什么？",
        answer="灯",
        aliases=["灯", "灯泡", "电灯"],
        hint="按一下按钮，或拉一下绳子，就能闪闪发光。",
    ),
    Riddle(
        question="我有两只脚，却不能走路。你知道我是什么吗？",
        answer="尺子",
        aliases=["尺子", "尺", "刻度尺"],
        hint="你用它来量长度和距离。",
    ),
    Riddle(
        question="我有四条腿，但我不会走。我每天都陪着你做功课。你知道我是什么吗？",
        answer="椅子",
        aliases=["椅子", "椅", "凳子"],
        hint="你坐在我上面，放松腰部。",
    ),
    Riddle(
        question="我可以跑，但没有脚。我可以唱，但没有嘴。你猜我是什么？",
        answer="水",
        aliases=["水", "溪水", "河流"],
        hint="没有它，没有生物能存活。",
    ),
    Riddle(
        question="白天睡觉，晚上工作。我住在你的房间里。你知道我是什么吗？",
        answer="蝙蝠",
        aliases=["蝙蝠", "蝠"],
        hint="我会发出超声波来导航，不会伤害人。",
    ),
    Riddle(
        question="我是一个盒子，但里面没有东西。打开我，你会听到许多声音。我是什么？",
        answer="收音机",
        aliases=["收音机", "广播", "收音"],
        hint="你可以调频道听新闻、音乐或故事。",
    ),
    Riddle(
        question="我在你的口袋里，但我不是钱。我能帮你记住重要的事情。你知道我是什么吗？",
        answer="手机",
        aliases=["手机", "电话", "手机"],
        hint="你每天都在看我，用我来聊天。",
    ),
]


# Word bank for word chain game - 30+ common Chinese words
# Organized to ensure good connectivity for 5-8 rounds
WORD_BANK: list[str] = [
    # Common starting words
    "天空",
    "空气",
    "气球",
    "球迷",
    "迷茫",
    "茫然",
    "然而",
    "而已",
    "已经",
    "经历",
    "历史",
    "史诗",
    "诗人",
    "人生",
    "生活",

    # Middle words
    "活动",
    "动物",
    "物理",
    "理想",
    "想法",
    "法律",
    "律师",
    "师傅",
    "傅说",
    "说话",
    "话题",
    "题目",
    "目标",
    "标准",
    "准备",

    # More connections
    "备战",
    "战争",
    "争议",
    "议论",
    "论坛",
    "坛子",
    "子女",
    "女儿",
    "儿童",
    "童年",
    "年轻",
    "轻松",
    "松树",
    "树木",
    "木头",

    # Additional words for backup
    "头脑",
    "脑力",
    "力量",
    "量化",
    "化学",
    "学生",
    "生日",
    "日期",
    "期待",
    "待遇",
]


def get_random_riddle_indices(count: int = 8) -> list[int]:
    """Get random riddle indices (not actually random, just sequential for first version)."""
    return list(range(min(count, len(RIDDLES))))


def normalize_text(text: str) -> str:
    """Normalize text for comparison: remove spaces, punctuation, convert to simplified Chinese."""
    # Remove common punctuation and spaces
    text = text.strip().lower()

    # Remove punctuation
    punctuation = "，。！？；：''""【】（）…、·"
    for p in punctuation:
        text = text.replace(p, "")

    # Remove spaces
    text = text.replace(" ", "").replace("\t", "").replace("\n", "")

    return text


def extract_word_from_user_input(text: str) -> str | None:
    """Extract the main word from user input, removing common prefixes."""
    text = text.strip()

    # Remove common prefixes
    prefixes = ["我接", "接", "词语是", "我说", "是", "我的词是"]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    # Remove punctuation
    text = normalize_text(text)

    # Return first continuous word (non-empty)
    if text:
        return text
    return None


def get_word_chain_starting_word() -> str:
    """Get the starting word for word chain game."""
    return "天空"


def find_next_word(last_char: str, exclude_words: set[str] | None = None) -> str | None:
    """Find next word from WORD_BANK starting with last_char."""
    if exclude_words is None:
        exclude_words = set()

    for word in WORD_BANK:
        if word not in exclude_words and word and word[0] == last_char:
            return word

    return None
