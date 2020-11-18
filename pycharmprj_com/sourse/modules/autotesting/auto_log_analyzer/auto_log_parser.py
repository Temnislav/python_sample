#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    @file      auto_log_parser.py

    @brief     Содержит класс для автоматического парсинга логов тестов

    @author    Пащенко Андрей <aschenko@starline.ru>

"""

from PyQt5 import QtCore
import collections
import copy
import os
import re
import source.modules.autotesting.auto_log_analyzer.shingles_parser as shingles_parser
from source.modules.autotesting.logger_api import *
from source.modules.testrail_api import *


class AutoLogParser(QtCore.QThread):
    """Класс, предназначенный для автоматического парсинга логов тестов

    Attributes:
        __logger: ссылка на logger

    """

    run1 = ""
    run2 = ""

    is_local = True

    def __init__(self, logger: LoggerApi=None):
        """Конструктор класса

        Attributes:
            :arg logger -- Ссылка на logger

        """
        super(AutoLogParser, self).__init__()
        self.__logger = logger
        self.__shingles_parser = shingles_parser.ShinglesParser(self.__logger)

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
        if list(kwargs.keys()).count('output') != 0:
            filename = kwargs['output']
            if filename:
                file = open(filename, 'a')
                file.write(data)
                file.close()
        if not self.__logger:
            print(data)
        else:
            if log_level == LogLevel.INFO:
                self.__logger.info_log(u'LOG PARSER :: %s %s' % (data, str(kwargs)))
            elif log_level == LogLevel.DEBUG:
                self.__logger.debug_log(u'LOG PARSER :: %s %s' % (data, str(kwargs)))
            else:
                self.__logger.trace_log(u'LOG PARSER :: %s %s' % (data, str(kwargs)))

    def __cmp_words(self,
                    first_word,
                    second_word):
        """Сравнение слов

        Attributes:
            :arg first_word -- Первое слово
            :arg second_word -- Второе слово

        Returns:
            :return Процент схожести

        """
        # if type(first_word) != unicode or type(second_word) != unicode:
        #     self.__log_print(self.__logger, source.modules.logger_api.LogLevel.INFO, u'Получено(ы) слово(а) не в unicode\n')
        #     return None
        maxt_word_len = max(len(first_word), len(second_word))
        same_ch_count = 0
        cmp_result = float()
        # print('word_len', len(first_word), len(second_word), maxt_word_len)
        for first_word_ch, second_word_ch in zip(first_word, second_word):
            if first_word_ch == second_word_ch:
                same_ch_count += 1
        # print('same_ch_count', same_ch_count)
        cmp_result = float(same_ch_count) / float(maxt_word_len)
        # print('cmp_result', cmp_result, maxt_word_len - same_ch_count)
        return (cmp_result, maxt_word_len - same_ch_count)

    def __cmp_lines(self,
                    first_line,
                    second_line):
        """Сравнение строк

        Attributes:
            :arg first_line -- Первая строка
            :arg second_line -- Вторая строка

        Returns:
            :return Процент схожести

        """
        # if type(first_line) != unicode or type(second_line) != unicode:
        #     self.__log_print(self.__logger, source.modules.logger_api.LogLevel.INFO, u'Получена(ы) строка(и) не в unicode\n')
        #     return None
        # self.__log_print(self.__logger, logger_api.LogLevel.INFO, u'Сравнение строк (%s, %s)\n' % (first_line, second_line))
        first_line_chunks = collections.Counter(first_line.lower().split())
        result = float()
        # print('first_line_chunks', first_line_chunks)
        second_line_chunks = collections.Counter(second_line.lower().split())
        # print('second_line_chunks', second_line_chunks)
        intersection_line_buf = dict()
        for first_line_chunk_key in first_line_chunks:
            intersection_line_buf.update({first_line_chunk_key: 0.0})
        for second_line_chunk_key in second_line_chunks:
            intersection_line_buf.update({second_line_chunk_key: 0.0})
        for first_line_chunk_key, first_line_chunk_val in first_line_chunks.items():
            for second_line_chunk_key, second_line_chunk_val in second_line_chunks.items():
                cmp_words_res = self.__cmp_words(first_line_chunk_key, second_line_chunk_key)
                if cmp_words_res and cmp_words_res[0] > 0.75 and cmp_words_res[1] < 4:
                    intersection_line_buf.update({first_line_chunk_key: float(min(first_line_chunk_val,
                                                                                  second_line_chunk_val)) / max(
                        first_line_chunk_val, second_line_chunk_val)})
                    if cmp_words_res[0] < 1.0 and list(intersection_line_buf.keys()).count(second_line_chunk_key) != 0:
                        intersection_line_buf.pop(second_line_chunk_key)
        # print('line_buf', intersection_line_buf)
        if len(intersection_line_buf) > 0:
            result = sum(intersection_line_buf.values())/len(intersection_line_buf)
        # self.__log_print(self.__logger, logger_api.LogLevel.TRACE, u'Результат сравнения строк %f\n' % result)
        return result

    def __find_fail_line(self,
                         file_dir,
                         file_name):
        """Поиск первой FAIL строки

        Attributes:
            :arg file_dir -- Директория файла
            :arg file_name -- Имя файла

        Returns:
            :return Найденная строка

        """
        result = None
        line_no = -1
        if file_dir:
            if not os.path.isdir(file_dir):
                self.__log_print(LogLevel.INFO, u'Директория %s не найдена\n' % str(file_dir))
                return None
            file_name = '%s/%s' % (file_dir, file_name)
        if not os.path.isfile(file_name):
            self.__log_print(LogLevel.INFO, u'Файл %s не найден\n' % str(file_name))
            return None
        failed_log_file = open(file_name, 'r')
        for line in failed_log_file:
            line_no += 1
            fail_line = line.find('FAIL')
            if fail_line != -1:
                result = line[fail_line:].strip('\n\r')
                break
        failed_log_file.close()
        # self.__log_print(self.__logger, logger_api.LogLevel.TRACE,
        #                  u'Строка найдена: %s (ID %d)\n' % (result, line_no))
        if not result:
            return None
        else:
            return (result, line_no)

    def __get_config_end(self, lines):
        """Получить номер первой строки, после смены настроек

        Attributes:
            :arg lines -- Список строк

        Returns:
            :return ID строки

        """
        line_id = 0
        for line in lines:
            line_id += 1
            if line.find('Message code:    2') != -1:
                return line_id
        return 0

    def __clear_log_tags(self, lines):
        """Отчистка меток лога (время, дата)

        Attributes:
            :arg lines -- Список строк

        Returns:
            :return Отчищенный от меток список

        """
        line_delimiter = ""
        lines_buf = list()
        for line in lines:
            line_delimiter = line.find('::')
            if line_delimiter != -1:
                lines_buf.append(line[line_delimiter:].strip('\n\r'))
            else:
                lines_buf.append(line.strip('\n\r'))
        return lines_buf

    def __get_case_from_filename(self, file_name):
        """Получить номер кейса из имени файла лога

        Attributes:
            :arg file_name -- Имя файла

        Returns:
            :return Номер кейса

        """
        search_result = re.search(r'log_', file_name)
        if not search_result:
            return None
        case_id = file_name[search_result.end():-4]
        while not case_id.isdigit():
            search_result = re.search(r'log_', file_name)
            if not search_result:
                return None
            case_id = file_name[search_result.end():-4]
        return int(case_id)

    def cmp_log_files(self,
                      first_dir,
                      first_name,
                      second_dir,
                      second_name,
                      **kwargs):
        """Сравнение двух логов

        Attributes:
            :arg first_dir -- Директория первого файла
            :arg first_name -- Имя первого файла
            :arg second_dir -- Директория второго файла
            :arg second_name -- Имя второго файла

        Returns:
            :return Процент сходства

        """
        first_fail = None
        second_fail = None
        first_file = None
        second_file = None
        first_file_lines = list()
        second_file_lines = list()
        cmp_sum = float()
        cmp_result = 0.0
        lines_count = int()
        shingles_cmp_result = 0.0
        dev_cmp_result = 0.0
        if list(kwargs.keys()).count('first_fail') != 0:
            first_fail = kwargs['first_fail']
        else:
            first_fail = self.__find_fail_line(first_dir, first_name)
        second_fail = self.__find_fail_line(second_dir, second_name)
        if not first_fail or not second_fail:
            return cmp_result
        fail_cmp = self.__cmp_lines(first_fail[0], second_fail[0])
        # print('fail_cmp %f\n' % fail_cmp)
        # print first_fail[0]
        if fail_cmp < 0.65:
            return cmp_result
        if first_dir and not first_name.startswith(first_dir):
            first_name = '%s/%s' % (first_dir, first_name)
        if second_dir and not second_name.startswith(second_dir):
            second_name = '%s/%s' % (second_dir, second_name)
        first_file = open(first_name, 'r')
        second_file = open(second_name, 'r')
        first_file_lines = first_file.readlines()
        first_file_lines = first_file_lines[self.__get_config_end(first_file_lines):first_fail[1]][::-1]
        second_file_lines = second_file.readlines()
        second_file_lines = second_file_lines[self.__get_config_end(second_file_lines):second_fail[1]][::-1]
        first_file_lines, second_file_lines = self.__clear_log_tags(first_file_lines), self.__clear_log_tags(second_file_lines)
        text_code = 'utf-8'
        text1 = ' '.join(first_file_lines)
        text_code = 'utf-8'
        text2 = ' '.join(second_file_lines)
        text_code = 'utf-8'

        shingles_cmp_result = self.__shingles_parser.cmp_texts(text1, text2)
        dev_cmp_result = self.cmp_device_log_files(first_name, second_name, first_dir)
        for first_file_line, second_file_line in zip(first_file_lines, second_file_lines):
            cmp_sum += self.__cmp_lines(first_file_line, second_file_line)
        first_file.close()
        second_file.close()
        lines_count = min(len(first_file_lines), len(second_file_lines))
        if lines_count > 0:
            if dev_cmp_result == 0.0:
                cmp_result = (shingles_cmp_result * 0.2 + fail_cmp * 0.3 + (cmp_sum / lines_count) * 0.5)
            else:
                cmp_result = (dev_cmp_result * 0.1 + shingles_cmp_result * 0.2 + fail_cmp * 0.3 + (cmp_sum / lines_count) * 0.4)
        self.__log_print(LogLevel.INFO, u'Результат сравнения (%s, %s): %f\n' % (first_name, second_name, cmp_result))
        return cmp_result

    def cmp_device_log_files(self,
                             log_file1,
                             log_file2,
                             dev_log_dir):
        """Сравнение двух логов устройства (метод Шинглов)

        Attributes:
            :arg log_file1 -- Путь до первого файла (лог теста)
            :arg log_file2 -- Путь до второго файла (лог теста)
            :arg dev_log_dir -- Директория логов устройства

        Returns:
            :return Процент сходства

        """
        case1 = self.__get_case_from_filename(log_file1)
        case2 = self.__get_case_from_filename(log_file2)

        dev_log1_flag = False
        dev_log2_flag = False

        dev_log_case1 = None
        dev_log_case2 = None

        if not case1 or not case2 or not dev_log_dir:
            return 0.0

        files = os.listdir(dev_log_dir)
        files = [file for file in files if file.find('parse_') != -1]

        if files and len(files) > 0:
            for file in files:
                if not dev_log1_flag and file.find('case_%d' % case1) != -1:
                    dev_log1_flag = True
                    dev_log_case1 = '%s/%s' % (dev_log_dir, file)
                if not dev_log2_flag and file.find('case_%d' % case2) != -1:
                    dev_log2_flag = True
                    dev_log_case2 = '%s/%s' % (dev_log_dir, file)
                if dev_log1_flag and dev_log2_flag:
                    break
        if not dev_log1_flag or not dev_log2_flag:
            return 0.0

        file2 = open(dev_log_case1, 'r')
        file1 = open(dev_log_case2, 'r')
        text1 = file1.read()
        text2 = file2.read()
        file1.close()
        file2.close()

        if not text1 or not text2:
            return 0.0

        shingles_cmp_result = self.__shingles_parser.cmp_texts(text1, text2)
        self.__log_print(LogLevel.INFO, u'Результат сравнения логов устройства по методу Шинглов (%d, %d): %f\n' % (case1, case2, shingles_cmp_result))
        return shingles_cmp_result

    def cmp_all_logs(self, file_dir, **kwargs):
        """Сравнение всех логов в директории

        Attributes:
            :arg first_dir -- Директория первого файла

        Returns:
            :return Результирующие данные

        """
        if list(kwargs.keys()).count('output') != 0:
            output = kwargs['output']
            if output and os.path.isfile(output):
                os.remove(output)
        self.__log_print(LogLevel.INFO, u'Запущено сравнение логов\n', **kwargs)
        if file_dir:
            if not os.path.isdir(file_dir):
                self.__log_print(LogLevel.INFO, u'Директория %s не найдена\n' % str(file_dir), **kwargs)
                return None
        cmp_result_dict = dict()
        cmp_case_dict = dict()
        interim_dict = dict()
        files = os.listdir(file_dir)
        files = [os.path.join(file_dir, file) for file in files]
        files = [file for file in files if os.path.isfile(file) and file.endswith('.log')]
        files_without_cmp = list()
        all_cmp_files = list()
        cmp_file_count = 1
        if not files:
            return None

        same_file_flag = False
        for file in files:
            # print self.__get_case_from_filename(file)
            for cmp_item in all_cmp_files:
                if file == cmp_item:
                    same_file_flag = True
                    break
            if same_file_flag:
                same_file_flag = False
                continue

            files_without_cmp = files[cmp_file_count:]
            cmp_file_count += 1
            first_fail = self.__find_fail_line(None, file)
            if first_fail:
                self.__log_print(LogLevel.INFO, u'Найденная ошибка: %s\n' % first_fail[0], **kwargs)
            cmp_result_dict.update({file : 1.0})
            cmp_case_dict.update({self.__get_case_from_filename(file): 1.0})
            for file_without_cmp in files_without_cmp:
                cmp_logs_res = self.cmp_log_files(file_dir, file, None, file_without_cmp, first_fail=first_fail)
                if cmp_logs_res > 0.50:
                    cmp_result_dict.update({file_without_cmp : cmp_logs_res})
                    cmp_case_dict.update({self.__get_case_from_filename(file_without_cmp): cmp_logs_res})
                    all_cmp_files.append(file_without_cmp)
                    files_without_cmp = filter(lambda x: x.find(file_without_cmp), files_without_cmp)
            if not first_fail:
                first_fail = (u'unrecognized',)
            if cmp_case_dict and len(cmp_case_dict) > 0:
                # interim_dict.update({u'%d %s' % (cmp_file_count, first_fail[0]) : copy.deepcopy(cmp_case_dict)})
                interim_dict.update({first_fail[0]: copy.deepcopy(cmp_case_dict)})
            self.__log_print(LogLevel.INFO, u'Результат сравнения: (%d) %s\n\n' % (len(cmp_case_dict), cmp_case_dict), **kwargs)
            cmp_result_dict.clear()
            cmp_case_dict.clear()
        self.__log_print(LogLevel.INFO, u'Результирующий словарь: (%d) %s\n\n' % (len(interim_dict), interim_dict), **kwargs)
        return interim_dict

    def cmp_logs_from_runs(self, first_file_dir, second_file_dir, **kwargs):
        """Сравнение всех логов в указанных директориях и сравнение между собой

        Attributes:
            :arg first_file_dir -- Первая сравниваемая директория (более ранний прогон)
            :arg second_file_dir -- вторая сравниваемая директория

        Returns:
            :return Результирующие данные

        """
        first_output = None
        second_output = None
        cmp_output = None
        if list(kwargs.keys()).count('first_output') != 0:
            first_output = kwargs['first_output']
            second_output = kwargs['second_output']
            cmp_output = kwargs['cmp_output']
        first_dict = self.cmp_all_logs(first_file_dir, output=first_output)
        second_dict = self.cmp_all_logs(second_file_dir, output=second_output)
        if type(first_dict) != dict or type(first_dict) != dict:
            return None
        cases_dict = dict()
        for second_key, second_val in second_dict.items():
            for first_key, first_val in first_dict.items():
                if type(first_key) != str or type(second_key) != str:
                    continue
                # first_key = first_key[first_key.find('FAIL'):]
                # print 'first_key', first_key
                # second_key = second_key[second_key.find('FAIL'):]
                if first_key == second_key:
                    intersection_cases = set(second_val) & set(first_val)
                    # old_fail = list(set(first_val) - intersection_cases)
                    new_fail = list(set(second_val) - intersection_cases)
                    # if len(old_fail) > 0 or len(new_fail) > 0:
                    #     cases_dict.update({first_key: {'OLD_FAILED_CASES': old_fail, 'NEW_FAILED_CASES': new_fail}})
                    if len(new_fail) > 0:
                        cases_dict.update({first_key: {'NEW_FAILED_CASES': new_fail}})
                    break
        intersection = set(second_dict) & set(first_dict)
        old_fail = set(first_dict) - intersection
        new_fail = set(second_dict) - intersection
        # if old_fail:
        #     for i in old_fail:
        #         cases_dict.update({i: {'OLD_FAILED_CASES': first_dict[i]}})
        if new_fail:
            for i in new_fail:
                cases_dict.update({i: {'NEW_FAILED_CASES': second_dict[i]}})
        if not cases_dict:
            return None
        self.__log_print(LogLevel.INFO, u'Результат сравнения двух прогонов (найдено различий: %d): \n\n' % len(cases_dict), output=cmp_output)
        for cases_dict_key, cases_dict_val in cases_dict.items():
            self.__log_print(LogLevel.INFO, u'%s:\n' % cases_dict_key, output=cmp_output)
            self.__log_print(LogLevel.INFO, u'%s\n\n' % str(cases_dict_val), output=cmp_output)
        return cases_dict

    # def auto_analyze(self, test_rail):
    #     """Запуск сравнения с консоли
    #
    #     Attributes:
    #         :arg test_rail -- ссылка на TestRail
    #
    #     """
    #     logs_dir = 'auto_analyzer_logs'
    #     if not os.path.isdir(logs_dir):
    #         os.mkdir(logs_dir)
    #     print(type(test_rail))
    #     print(u"Сделать анализ на базе 2-х прогонов (сравнение)? (1 - режим сравнения, 0 - нет)")
    #     cmp_type = raw_input('>>>')
    #     while not cmp_type.isdigit() or (cmp_type != '1' and cmp_type != '0'):
    #         print(u"Неверные данные (необходимо ввести число 1 или 0)")
    #         cmp_type = raw_input('>>>')
    #     print(u"На базе каких данных необходимо сделать анализ? (1 - прогон, 0 - сформированные логи)")
    #     analytic_type = raw_input('>>>')
    #     while not analytic_type.isdigit() or (analytic_type != '1' and analytic_type != '0'):
    #         print(u"Неверные данные (необходимо ввести число 1 или 0)")
    #         analytic_type = raw_input('>>>')
    #
    #     cmp_type_str = u'прогона'
    #     if cmp_type == '1':
    #         cmp_type_str = u'первого прогона (более ранний)'
    #     print(u"Введите номер %s" % cmp_type_str)
    #     run1 = raw_input('>>>')
    #     while not run1.isdigit():
    #         print(u"Неверные данные (необходимо ввести число)")
    #         run1 = raw_input('>>>')
    #
    #     run2 = str()
    #     if cmp_type == '1':
    #         print(u"Введите номер второго прогона (более поздний)")
    #         run2 = raw_input('>>>')
    #         while not run2.isdigit():
    #             print(u"Неверные данные (необходимо ввести число)")
    #             run2 = raw_input('>>>')
    #         if analytic_type == '1':
    #             test_rail.create_logs_from_run('failed_logs', int(run1))
    #             test_rail.create_logs_from_run('failed_logs', int(run2))
    #         self.cmp_logs_from_runs('failed_logs/%s' % str(run1),
    #                                 'failed_logs/%s' % str(run2),
    #                                 first_output = '%s/auto_analyzer_log_%s.log' % (logs_dir, str(run1)),
    #                                 second_output ='%s/auto_analyzer_log_%s.log' % (logs_dir, str(run2)),
    #                                 cmp_output = '%s/auto_analyzer_log_cmp_%s_%s.log' % (logs_dir, str(run1), str(run2)))
    #     else:
    #         if analytic_type == '1':
    #             test_rail.create_logs_from_run('failed_logs', int(run1))
    #         self.cmp_all_logs('failed_logs/%s' % str(run1), output='%s/%s' % (logs_dir, str(run1)))

    def run(self):
        logs_dir = 'auto_analyzer_logs'
        if not os.path.isdir(logs_dir):
            os.mkdir(logs_dir)

        if self.run1 != "" and self.run2 != "":
            if not self.is_local:
                self.create_logs_from_run('failed_logs', int(self.run1))
                self.create_logs_from_run('failed_logs', int(self.run2))
            self.cmp_logs_from_runs('failed_logs/%s' % str(self.run1),
                                    'failed_logs/%s' % str(self.run2),
                                    first_output='%s/auto_analyzer_log_%s.log' % (logs_dir, str(self.run1)),
                                    second_output='%s/auto_analyzer_log_%s.log' % (logs_dir, str(self.run2)),
                                    cmp_output='%s/auto_analyzer_log_cmp_%s_%s.log' % (logs_dir, str(self.run1), str(self.run2)))
        else:
            if not self.is_local:
                self.create_logs_from_run('failed_logs', int(self.run1))
            self.cmp_all_logs('failed_logs/%s' % str(self.run1), output='%s/%s' % (logs_dir, str(self.run1)))

    def create_logs_from_run(self, path, run_id):
        """Создать логи на базе прогона

        Arguments:
            :arg path -- директория
            :arg run_id -- номер прогона
        """
        self.__logger.info_log(u'Создание логов из прогона\n')
        if not os.path.exists('%s/%s' % (path, run_id)):
            self.__logger.debug_log(u'Директории (%s/%s) не существует, создание директории\n' % (path, run_id))
            os.makedirs('%s/%s' % (path, run_id))

        tests = get_tests(run_id)
        failed_tests = dict()
        for test in tests:
            if test['status_id'] == FAILED:
                failed_tests.update({test['id'] : test['case_id']})
        for failed_test_key, failed_test_val in failed_tests.items():
            failed_logs_file = open('%s/%s/log_%s.log' % (path, run_id, str(failed_test_val)), 'w', encoding="utf-8")
            self.__logger.debug_log(u'Запись в файл %s/%s/log_%s.log\n' % (path, run_id, str(failed_test_val)))
            results = get_results(failed_test_key)
            comment = None
            for result in results:
                comment = result['comment']
                if comment and len(comment) > 10:
                    break
            if comment:
                failed_logs_file.write(comment)
            failed_logs_file.close()

if __name__ == '__main__':
    log_parser = AutoLogParser()
    # log_parser.cmp_lines(log_parser.find_fail_line('C:\Job/SerialForAr/Serial_for_arduino20/failed_logs', 'log_15226.log'), log_parser.find_fail_line('C:\Job/SerialForAr/Serial_for_arduino20/failed_logs', 'log_19825.log'))
    # print log_parser.find_fail_line('C:\Job/SerialForAr/Serial_for_arduino20/failed_logs', 'log_15226.log')
    # log_parser.cmp_log_files('C:\Job/SerialForAr/Serial_for_arduino20/failed_logs', 'log_12238.log', 'C:\Job/SerialForAr/Serial_for_arduino20/failed_logs', 'log_12257.log')

    # log_parser.cmp_all_logs('C:\Job/SerialForAr/Serial_for_arduino21/failed_logs/2863')
    # log_parser.cmp_logs_from_runs('C:\\Users\\User\\YandexDisk\\failed_logs\\2905',
    #                               'C:\\Users\\User\\YandexDisk\\failed_logs\\2907')
    log_parser.cmp_logs_from_runs('C:\Job/SerialForAr/Serial_for_arduino21/failed_logs/2863',
                                  'C:\Job/SerialForAr/Serial_for_arduino21/failed_logs/2783',
                                  first_output='parse_2863.log',
                                  second_output='parse_2783.log',
                                  cmp_output='cmp_2863_2783.log')

    # log_parser.cmp_device_log_files('log_19882.log', 'log_19871.log', 'C:\Job/SerialForAr/Serial_for_arduino20/loger/log/parser')
    # os.rename('C:\Job/SerialForAr/Serial_for_arduino20/loger/log/parser/serv_parser/IMEI_20170517120534/17_05_2017/parse_20170517120534_05_17_12_05_37_load_0.txt','C:\Job/SerialForAr/Serial_for_arduino20/loger/log/parser/serv_parser/IMEI_20170517120534/17_05_2017/case_111_parse_20170517120534_05_17_12_05_37_load_0.txt')

    import shutil

    # shutil.move('C:\Job\SerialForAr/Serial_for_arduino20/loger/log/parser/serv_parser/IMEI_20170517131002/17_05_2017/case_12203_parse_20170517131002_05_17_13_10_04_load_0.txt', 'C:\Job/SerialForAr/Serial_for_arduino20/failed_logs/2691')