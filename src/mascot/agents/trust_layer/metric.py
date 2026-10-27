from dataclasses import dataclass, field
from datetime import date


@dataclass
class Metric:
    """
    Одна метрика с провенансом (происхождением).

    Идея: любое число в системе должно знать,
    откуда оно взялось, за какой период и насколько ему можно верить.
    Это прямое требование ТЗ: «фиксировать происхождение каждой метрики».
    """

    # commits_count, tasks_closed
    name: str                          
    # 42, 0.85 - само значение
    value: float                       

    # git, jira, lms, hr
    source: str                       
    # начало периода наблюдения
    period_start: date                 
    # конец периода наблюдения
    period_end: date                   

    # сколько наблюдений легло в основу
    sample_size: int = 1       
           
    confidence: float = 1.0        

    @property
    def is_sufficient(self) -> bool:
        """
        Достаточно ли данных для вывода.
        ТЗ: «учитывать период и достаточность данных».
        Порог пока простой — потом можно вынести в config.
        """
        return self.sample_size >= 5 and self.confidence >= 0.5

    @property
    def period_days(self) -> int:
        """Длительность периода в днях — часто нужно для нормализации."""
        return (self.period_end - self.period_start).days + 1