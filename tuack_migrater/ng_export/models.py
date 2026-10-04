from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union, Literal
from enum import Enum
import re


def _to_kebab(s: str) -> str:
    return re.sub(r'_', '-', s)


class ProblemType(str, Enum):
    program = "program"
    output = "output"
    interactive = "interactive"


class DmkConfig(str, Enum):
    skip = "skip"
    input = "input"
    output = "output"
    on = "on"


class ScorePolicy(str, Enum):
    sum = "sum"
    max = "max"
    min = "min"


class GeneratorConfig(BaseModel):
    gen: str = Field(alias="gen")
    deps: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


class GeneratorConfigPair(BaseModel):
    data: GeneratorConfig
    sample: Optional[GeneratorConfig] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


class CheckerConfig(BaseModel):
    source: str
    deps: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


class CheckerConfigPair(BaseModel):
    data: CheckerConfig
    sample: Optional[CheckerConfig] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


class InteractiveConfig(BaseModel):
    grader: str
    header: str
    sample_grader: Optional[str] = Field(None, alias="sample grader")
    dmk_grader: Optional[str] = Field(None, alias="dmk grader")

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


class SingleDataItem(BaseModel):
    id: int
    score: int = 0
    subtask: int = 0
    input: Optional[str] = None
    output: Optional[str] = None
    args: Dict = Field(default_factory=dict)
    dmk: Optional[DmkConfig] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


class BundleDataItem(BaseModel):
    id: List[int]
    score: int = 0
    subtask: int = 0
    args: Dict = Field(default_factory=dict)
    dmk: Optional[DmkConfig] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


DataItem = Union[SingleDataItem, BundleDataItem]


class SampleItem(BaseModel):
    id: int
    input: Optional[str] = None
    output: Optional[str] = None
    args: Dict = Field(default_factory=dict)
    dmk: Optional[DmkConfig] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


class ExpectedScore(BaseModel):
    pass


class TestCase(BaseModel):
    expected: str = ""
    path: str = ""

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


# ── Problem ──

class ProblemConfigFile(BaseModel):
    version: Literal[7] = 7
    folder: Literal["problem"] = "problem"
    type: ProblemType = ProblemType.program
    name: str = ""
    title: str = ""
    time_limit: float = Field(1.0, alias="time limit")
    memory_limit: str = Field("512 MiB", alias="memory limit")
    dmk: DmkConfig = DmkConfig.on
    args: Dict = Field(default_factory=dict)
    interactive: Optional[InteractiveConfig] = None
    generator: Optional[GeneratorConfigPair] = None
    samples: List[SampleItem] = Field(default_factory=list)
    data: List[DataItem] = Field(default_factory=list)
    subtasks: Dict[str, ScorePolicy] = Field(default_factory=lambda: {"0": ScorePolicy.sum})
    tests: Dict[str, TestCase] = Field(default_factory=dict)
    checker: Optional[CheckerConfigPair] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


# ── Day ──

class ContestDayConfigFile(BaseModel):
    version: Literal[7] = 7
    folder: Literal["day"] = "day"
    name: str = ""
    subdir: List[str] = Field(default_factory=list)
    title: str = ""
    compile: Dict[str, str] = Field(default_factory=dict)
    start_time: Optional[List[int]] = Field(None, alias="start time")
    end_time: Optional[List[int]] = Field(None, alias="end time")
    use_pretest: Optional[bool] = None
    noi_style: Optional[bool] = None
    file_io: Optional[bool] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}


# ── Contest ──

class ContestConfigFile(BaseModel):
    version: Literal[7] = 7
    folder: Literal["contest"] = "contest"
    name: str = ""
    subdir: List[str] = Field(default_factory=list)
    title: str = ""
    short_title: str = Field("", alias="short title")
    use_pretest: Optional[bool] = None
    noi_style: Optional[bool] = None
    file_io: Optional[bool] = None

    model_config = {"populate_by_name": True, "alias_generator": _to_kebab}
