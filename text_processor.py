#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль обработки и фильтрации текста для Telegram-бота
Включает функции очистки мата, токсичности и нормализации текста
"""

import re
import string
from typing import List, Tuple, Dict

class TextProcessor:
    """Класс для обработки и фильтрации текста"""
    
    def __init__(self):
        # Словарь мата и нецензурных выражений
        self.profanity_words = [
            # Основные маты
            'блядь', 'блять', 'бля', 'блд', 'b***', 'bl***',
            'сука', 'сучка', 'сук', 'сч', 's***',
            'пизда', 'пздц', 'пзд', 'p***',
            'хуй', 'хй', 'хер', 'x***', 'h***',
            'ебать', 'ебал', 'ебет', 'ебут', 'еб', 'ебн', 'ебл', 'e***',
            'говно', 'гвн', 'g***',
            'дерьмо', 'дрм', 'd***',
            'срать', 'срет', 'ср', 's***',
            'пидор', 'пидар', 'пдр', 'p***',
            'мудак', 'мдк', 'm***',
            'козел', 'кзл', 'k***',
            'сволочь', 'свл', 's***',
            'тварь', 'твр', 't***',
            'гад', 'гд', 'g***',
            'падла', 'пдл', 'p***',
            'урод', 'урд', 'u***',
            
            # Вариации и замены
            'б***ь', 'с***а', 'п***а', 'х***', 'е***ь',
            'бл*дь', 'с*ка', 'п*зда', 'х*й', 'еб*ть',
            'блять', 'сцука', 'пездец', 'хрен', 'ебать',
            
            # Обходы цензуры
            'бл@дь', 'с@ка', 'п@зда', 'х@й', 'еб@ть',
            'бл4дь', 'с4ка', 'п1зда', 'х4й', 'еб4ть',
            'блядина', 'сукин', 'пиздец', 'хуйня', 'ебучий'
        ]
        
        # Агрессивные слова и фразы
        self.aggressive_words = [
            'убью', 'убить', 'убийство', 'убийца',
            'ненавижу', 'ненависть', 'ненавистный',
            'идиот', 'идиотка', 'идиотский',
            'дурак', 'дура', 'дурацкий',
            'кретин', 'кретинка', 'кретинский',
            'тупой', 'тупая', 'тупость',
            'долбоеб', 'долбоебка', 'долбоебский',
            'придурок', 'придурочный',
            'дебил', 'дебилка', 'дебильный',
            'имбецил', 'имбецилка',
            'олигофрен', 'олигофренка',
            'психопат', 'психопатка',
            'маньяк', 'маньячка',
            'уродина', 'уродливый',
            'мразь', 'мерзавец', 'мерзавка',
            'подонок', 'подонка',
            'негодяй', 'негодяйка',
            'скотина', 'скот',
            'животное', 'зверь'
        ]
        
        # Замены для агрессивных слов
        self.aggressive_replacements = {
            r'\bубью\b': 'очень недоволен',
            r'\bубить\b': 'крайне недоволен',
            r'\bубийство\b': 'крайне негативное поведение',
            r'\bненавижу\b': 'недоволен',
            r'\bненависть\b': 'недовольство',
            r'\bидиот\w*\b': 'некомпетентный человек',
            r'\bдурак\w*\b': 'некомпетентный человек',
            r'\bкретин\w*\b': 'некомпетентный человек',
            r'\bтупой\w*\b': 'некомпетентный',
            r'\bтупая\b': 'некомпетентная',
            r'\bтупость\b': 'некомпетентность',
            r'\bдолбоеб\w*\b': 'некомпетентный человек',
            r'\bпридурок\w*\b': 'некомпетентный человек',
            r'\bдебил\w*\b': 'некомпетентный человек',
            r'\bимбецил\w*\b': 'некомпетентный человек',
            r'\bолигофрен\w*\b': 'некомпетентный человек',
            r'\bпсихопат\w*\b': 'неадекватный человек',
            r'\bманьяк\w*\b': 'неадекватный человек',
            r'\bуродина\b': 'неприятный человек',
            r'\bуродливый\b': 'неприятный',
            r'\bмразь\b': 'неприятный человек',
            r'\bмерзавец\w*\b': 'неприятный человек',
            r'\bподонок\w*\b': 'неприятный человек',
            r'\bнегодяй\w*\b': 'неприятный человек',
            r'\bскотина\b': 'неприятный человек',
            r'\bскот\b': 'неприятный человек',
            r'\bживотное\b': 'неприятный человек',
            r'\bзверь\b': 'неприятный человек'
        }
        
        # Паттерны для обнаружения замаскированного мата
        self.masked_patterns = [
            r'[бb][л*@#$%^&!]{1,3}[яa]',
            r'[сs][у*@#$%^&!]{1,3}[кk]',
            r'[пp][и*@#$%^&!]{1,3}[зz]',
            r'[хh][у*@#$%^&!]{1,3}[йy]',
            r'[еe][б*@#$%^&!]{1,3}[аa]'
        ]
    
    def clean_profanity(self, text: str) -> str:
        """Очистка текста от мата"""
        cleaned_text = text.lower()
        
        # Удаляем прямые вхождения
        for word in self.profanity_words:
            pattern = rf'\b{re.escape(word)}\w*\b'
            cleaned_text = re.sub(pattern, '[УДАЛЕНО]', cleaned_text, flags=re.IGNORECASE)
        
        # Удаляем замаскированный мат
        for pattern in self.masked_patterns:
            cleaned_text = re.sub(pattern, '[УДАЛЕНО]', cleaned_text, flags=re.IGNORECASE)
        
        return cleaned_text
    
    def reduce_aggression(self, text: str) -> str:
        """Снижение агрессии в тексте"""
        processed_text = text
        
        # Применяем замены агрессивных слов
        for pattern, replacement in self.aggressive_replacements.items():
            processed_text = re.sub(pattern, replacement, processed_text, flags=re.IGNORECASE)
        
        # Убираем множественные восклицательные знаки
        processed_text = re.sub(r'!{2,}', '!', processed_text)
        
        # Убираем CAPS LOCK (кроме аббревиатур)
        words = processed_text.split()
        for i, word in enumerate(words):
            if len(word) > 3 and word.isupper() and word.isalpha():
                words[i] = word.capitalize()
        processed_text = ' '.join(words)
        
        return processed_text
    
    def normalize_text(self, text: str) -> str:
        """Нормализация текста"""
        # Убираем лишние пробелы
        normalized = re.sub(r'\s+', ' ', text.strip())
        
        # Убираем повторяющиеся знаки препинания
        normalized = re.sub(r'\.{2,}', '...', normalized)
        normalized = re.sub(r'\?{2,}', '?', normalized)
        normalized = re.sub(r',{2,}', ',', normalized)
        
        # Исправляем пробелы перед знаками препинания
        normalized = re.sub(r'\s+([,.!?;:])', r'\1', normalized)
        normalized = re.sub(r'([,.!?;:])\s*', r'\1 ', normalized)
        
        # Убираем лишние пробелы в конце
        normalized = normalized.strip()
        
        return normalized
    
    def check_toxicity(self, text: str) -> Tuple[bool, float, List[str]]:
        """Простая проверка токсичности текста"""
        issues = []
        toxicity_score = 0.0
        
        text_lower = text.lower()
        
        # Проверяем мат
        profanity_count = 0
        for word in self.profanity_words:
            if word in text_lower:
                profanity_count += 1
                toxicity_score += 0.3
        
        if profanity_count > 0:
            issues.append(f"Обнаружена нецензурная лексика ({profanity_count} слов)")
        
        # Проверяем агрессию
        aggression_count = 0
        for word in self.aggressive_words:
            if word in text_lower:
                aggression_count += 1
                toxicity_score += 0.2
        
        if aggression_count > 0:
            issues.append(f"Обнаружена агрессивная лексика ({aggression_count} слов)")
        
        # Проверяем CAPS LOCK
        caps_words = [word for word in text.split() if len(word) > 3 and word.isupper()]
        if len(caps_words) > 2:
            issues.append("Чрезмерное использование заглавных букв")
            toxicity_score += 0.1
        
        # Проверяем множественные восклицательные знаки
        if '!!!' in text:
            issues.append("Чрезмерное использование восклицательных знаков")
            toxicity_score += 0.1
        
        # Ограничиваем оценку
        toxicity_score = min(toxicity_score, 1.0)
        
        is_toxic = toxicity_score > 0.5
        
        return is_toxic, toxicity_score, issues
    
    def process_complaint_text(self, text: str, max_length: int = 1000) -> Dict[str, any]:
        """Полная обработка текста жалобы"""
        original_text = text
        
        # Проверяем токсичность оригинала
        is_toxic, toxicity_score, issues = self.check_toxicity(original_text)
        
        # Обрабатываем текст
        processed_text = self.clean_profanity(text)
        processed_text = self.reduce_aggression(processed_text)
        processed_text = self.normalize_text(processed_text)
        
        # Ограничиваем длину
        if len(processed_text) > max_length:
            processed_text = processed_text[:max_length-3] + "..."
        
        # Проверяем результат
        final_is_toxic, final_toxicity_score, final_issues = self.check_toxicity(processed_text)
        
        return {
            'original_text': original_text,
            'processed_text': processed_text,
            'original_toxicity': {
                'is_toxic': is_toxic,
                'score': toxicity_score,
                'issues': issues
            },
            'final_toxicity': {
                'is_toxic': final_is_toxic,
                'score': final_toxicity_score,
                'issues': final_issues
            },
            'changes_made': original_text != processed_text,
            'length_original': len(original_text),
            'length_final': len(processed_text)
        }
    
    def suggest_improvements(self, text: str) -> List[str]:
        """Предложения по улучшению текста"""
        suggestions = []
        
        # Проверяем длину
        if len(text) < 20:
            suggestions.append("Добавьте больше деталей в описание")
        
        # Проверяем структуру
        if '.' not in text and '!' not in text and '?' not in text:
            suggestions.append("Разделите текст на предложения")
        
        # Проверяем конкретность
        vague_words = ['что-то', 'как-то', 'где-то', 'когда-то', 'кто-то']
        if any(word in text.lower() for word in vague_words):
            suggestions.append("Будьте более конкретны в описании")
        
        # Проверяем эмоциональность
        if text.count('!') > 3:
            suggestions.append("Используйте более спокойный тон")
        
        return suggestions

# Функция для тестирования
def test_processor():
    """Тестирование процессора текста"""
    processor = TextProcessor()
    
    test_texts = [
        "Этот водитель полный идиот и мудак!",
        "ВОДИТЕЛЬ ВЕДЕТ СЕБЯ КАК ЖИВОТНОЕ!!!",
        "Он такой тупой, что даже не понимает правила",
        "Нормальное описание без проблем",
        "Водитель нарушил правила и вел себя неадекватно"
    ]
    
    for text in test_texts:
        result = processor.process_complaint_text(text)
        print(f"Оригинал: {result['original_text']}")
        print(f"Обработано: {result['processed_text']}")
        print(f"Токсичность: {result['final_toxicity']['score']:.2f}")
        print(f"Проблемы: {result['final_toxicity']['issues']}")
        print("-" * 50)

if __name__ == "__main__":
    test_processor()

