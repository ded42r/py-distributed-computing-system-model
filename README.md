Реализация распределенной вычислительной системы на Python 2.7.

Постановка задачи находится в разделе _Задача_. 

# Описание 

* Вычислитель командой, где опция -s для указания файла конфига \
`python run_calculator.py -s config.json`
* Клиент запускается с помощью _run_client.py_
* Диспетчер запускается с помощью _run_dispatcher.py_
* Можно использовать docker-compose, описание сервисов в файле docker-compose.yml.
* Протокол обмена для всех процессов один и описан в net_protocol. Процессы обмениваются командами в формате json. JSON, а например не бинарный формат выбран для упрощения, т.к. как это модель системы.
* Описание настроек для клиента, вычислителя, диспетчера находятся в папке _docs_.
* В папке _config_ примеры конфигов. 
* Если клиенту отправить сигнал SIGINT, то он мягко завершит работу и выведет статистику
* Для поддержки аннотаций типов нужно установить модуль _typing_ из _requirements-dev.txt_. Необязательный шаг.

# Задача 
Построить модель распределенной отказоустойчивой вычислительной системы.

Три типа процессов:
* Клиент
* Диспетчер
* Вычислитель

Примечания:
* Протокол взаимодействия между процессами(формат пакетов) - на усмотрение разработчика. 
* Ограничение - в качестве транспорта должен использоваться UDP.
* Исходный код должен быть совместим с версией Python 2.7.

## Клиент
Знает адрес и порт диспетчера, со случайной периодичностью, задаваемой в конфиге клиента, посылает диспетчеру условное задание.

Каждый клиент ведет статистику:
* сколько запросов было отправлено, 
* сколько ответов было получено, 
* сколько запросов осталось без ответа, 
* минимальное, среднее и максимальное время получения ответа.

## Диспетчер
* Обрабатывает UDP-пакеты от клиентов и вычислителей.
* Слушает на порту, задаваемом в конфиге диспетчера.  
* Получая запрос от клиента - выбирает доступного вычислителя, посылает ему задание. 
* Получая ответ от вычислителя - возвращает ответ клиенту, инициировавшему конкретный запрос
* Требуется обеспечить динамическую регистрацию вычислителей диспетчером
* отслеживание неработоспособности отдельных вычислителей, 
* обеспечить гарантированное выполнение запросов 
    * если выбранный для обработки конкретного клиентского запроса вычислитель за заданный промежуток не ответил - диспетчер посылает запрос другому свободному вычислителю, либо держит запрос в очереди, пока не истечет заданный таймаут).

## Вычислитель
* Слушает на порту, задаваемом в конфиге вычислителя. 
* При получении задания эмулирует длительные вычисления, засыпая на период, значение которого определяется случайным образом из интервала, задаваемого в конфиге. 
* По окончании паузы посылает ответ диспетчеру с условным результатом вычислений. 
* Вычислитель может периодически "выходить из строя", переставая принимать запросы и отвечать диспетчеру. 
* Вероятность и длительность периода неработоспособности конфигурируются. 
* Работоспособные вычислители с заданной периодичностью посылают диспетчеру уведомления о своей доступности. 
* Ответ с результатом вычислений также является сигналом диспетчеру о работоспособности конкретного экземпляра вычислителя.
* Требуется обеспечить динамическую регистрацию вычислителей диспетчером
