#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    @file      shingles_parser.py

    @brief     Содержит класс для автоматического парсинга логов тестов по алгоритму Шинглов

    @author    Пащенко Андрей <paschenko@starline.ru>

"""

import binascii
from source.modules.autotesting.logger_api import *

class ShinglesParser(object):
    """Класс, предназначенный для автоматического парсинга логов тестов по алгоритму Шинглов

    Attributes:
        SHINGLE_LEN: длина шингла
        __logger: ссылка на logger

    """

    SHINGLE_LEN = 10

    def __init__(self, logger:LoggerApi=None):
        """Конструктор класса

        Attributes:
            :arg logger -- Ссылка на logger

        """
        self.__logger = logger

    def __log_print(self,
                    log_level,
                    data,
                    **kwargs):
        """Вывод лога с добавлением префикса LOG PARSER в консоль или файл, если logger == None, вывод через print

        Attributes:
            :arg logger -- Ссылка на logger
            :arg log_level -- Уровень логирования
            :arg data -- Выводимые данные

        """
        if log_level == LogLevel.INFO:
            self.__logger.info_log(u'LOG PARSER :: %s %s' % (data, str(**kwargs)))
        elif log_level == LogLevel.DEBUG:
            self.__logger.debug_log(u'LOG PARSER :: %s %s' % (data, str(**kwargs)))
        else:
            self.__logger.trace_log(u'LOG PARSER :: %s %s' % (data, str(**kwargs)))

    def __canonize(self, source):
        """Канонизация текста (чистка от стоп-слов/стоп-символов)

        Attributes:
            :arg source -- Текст

        Returns:
            :return Список после чистки от указанных слов

        """
        stop_symbols = '.,!?:;-\n\r()<>1234567890'

        stop_words = (u'это', u'как', u'так',
                      u'и', u'в', u'над',
                      u'к', u'до', u'не',
                      u'на', u'но', u'за',
                      u'то', u'с', u'ли',
                      u'а', u'во', u'от',
                      u'со', u'для', u'о',
                      u'же', u'ну', u'вы',
                      u'бы', u'что', u'кто',
                      u'он', u'она', u'при',
                      u'LOG_DEBUG', u'LOG_INFO',
                      u'LOG_TRACE')

        return ([x for x in [y.strip(stop_symbols) for y in source.lower().split()] if x and (x not in stop_words)])

    def __gen_shingle(self, source):
        """Разбиение текста на шинглы

        Attributes:
            :arg source -- Текст

        Returns:
            :return Список (хэшированные шинглы)

        """
        out = []
        for i in range(len(source) - (self.SHINGLE_LEN - 1)):
            out.append(binascii.crc32(' '.join([x for x in source[i:i + self.SHINGLE_LEN]]).encode('utf-8')))
        return out

    def __compaire(self, source1, source2):
        """Сравнение текстов

        Attributes:
            :arg source1 -- Текст 1
            :arg source2 -- Текст 2

        Returns:
            :return Результат сравнения в процентах

        """
        same = 0
        source_temp = None
        if len(source1) < 1 or len(source2) < 1:
            return 0.0
        if len(source1) > len(source2):
            source_temp = source1
            source1 = source2
            source2 = source_temp
        for i in range(len(source1)):
            if source1[i] in source2:
                same = same + 1
        return same * 2 / float(len(source1) + len(source2))

    def cmp_texts(self, text1, text2):
        """Сравнение текстов

        Attributes:
            :arg text1 -- Текст 1
            :arg text2 -- Текст 2

        Returns:
            :return Результат сравнения в процентах

        """
        if not text1 or not text2:
            return 0.0
        cmp1 = self.__gen_shingle(self.__canonize(text1))
        cmp2 = self.__gen_shingle(self.__canonize(text2))
        return self.__compaire(cmp1, cmp2)

if __name__ == '__main__':
    shingles = ShinglesParser()

    file1 = open('C:\Job/SerialForAr/Serial_for_arduino20/failed_logs/2691/case_12204_parse_20170517153355_05_17_15_33_57_load_0.txt', 'r')
    # file1 = open('C:\\Job\\SerialForAr\\Serial_for_arduino20\\loger\\log\\parser\\serv_parser\\IMEI_20170517011513\\17_05_2017\\parse_20170517011513_05_17_01_15_15_load_0.txt', 'r') # нет
    file2 = open('C:\Job/SerialForAr/Serial_for_arduino20/failed_logs/2691/case_12203_parse_20170517153053_05_17_15_30_56_load_0.txt', 'r')

    # file1 = open('C:\\Job\\SerialForAr\\Serial_for_arduino20\\failed_logs\\2701\\log_12302.log')
    # file2 = open('C:\\Job\\SerialForAr\\Serial_for_arduino20\\failed_logs\\2701\\log_12301.log')

    text1 = file1.read().decode('cp1251')
    text2 = file2.read().decode('cp1251')
    file1.close()
    file2.close()

    print(shingles.cmp_texts(text1, text2))