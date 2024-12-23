# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import glob
import os
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

import dash_bootstrap_components as dbc
import hydra
from dash import Dash
from flask import Flask
from omegaconf import OmegaConf
from settings.constants import (
    CODE_BEGIN,
    CODE_END,
    CODE_OUTPUT_BEGIN,
    CODE_OUTPUT_END,
    CODE_SEPARATORS,
    CONFIGS_FOLDER,
    RETRIEVAL,
    RETRIEVAL_FIELDS,
    TEMPLATES_FOLDER,
    UNDEFINED,
)
from settings.inspector_config import InspectorConfig
from utils.common import initialize_default

from nemo_skills.prompt.few_shot_examples import examples_map
from nemo_skills.prompt.utils import PromptConfig, get_prompt, load_config
from nemo_skills.utils import setup_logging

setup_logging()
config_path = os.path.join(os.path.abspath(Path(__file__).parents[1]), "settings")

config = {}

generation_config_dir = Path(__file__).resolve().parents[2].joinpath("nemo_skills", "inference").resolve()
os.environ["config_dir"] = str(generation_config_dir)


def list_yaml_files(folder_path):
    yaml_files = glob.glob(os.path.join(folder_path, '**', '*.yaml'), recursive=True)

    yaml_files_relative = [os.path.relpath(file, folder_path) for file in yaml_files]

    return yaml_files_relative


def get_specific_fields(dict_cfg: Dict, fields: List[Dict]) -> Dict:
    retrieved_values = {}
    for key, value in dict_cfg.items():
        if key in fields:
            retrieved_values[key] = value
        if isinstance(value, Dict):
            retrieved_values = {
                **retrieved_values,
                **get_specific_fields(value, fields),
            }
    return retrieved_values


def update_nested_dict(dict1, dict2):
    for key, value in dict2.items():
        # If the value is a dictionary, call the function recursively
        if isinstance(value, dict) and key in dict1 and isinstance(dict1[key], dict):
            update_nested_dict(dict1[key], value)
        else:
            # Otherwise, directly update the value
            dict1[key] = value


@hydra.main(version_base=None, config_path=config_path, config_name="inspector_config")
def set_config(cfg: InspectorConfig) -> None:
    global config
    if not cfg.input_file and not cfg.dataset and not cfg.split:
        cfg.dataset = UNDEFINED
        cfg.split = UNDEFINED

    cfg.output_file = UNDEFINED

    examples_types = list(examples_map.keys())

    if "server_type" not in cfg.server:
        cfg.server = OmegaConf.create({"server_type": UNDEFINED})

    if cfg.server.server_type != 'openai' and cfg.prompt_template is None:
        cfg.prompt_template = UNDEFINED

    config['nemo_inspector'] = asdict(OmegaConf.to_object(cfg))

    config['nemo_inspector']['types'] = {
        "prompt_config": [UNDEFINED] + list_yaml_files(os.path.join(CONFIGS_FOLDER)),
        "prompt_template": [UNDEFINED] + list_yaml_files(os.path.join(TEMPLATES_FOLDER)),
        "examples_type": [UNDEFINED, RETRIEVAL] + examples_types,
        "retrieval_field": [""],
    }
    conf_path = (
        config['nemo_inspector']['prompt_config']
        if os.path.isfile(str(config['nemo_inspector']['prompt_config']))
        else os.path.join(CONFIGS_FOLDER, f"{config['nemo_inspector']['prompt_config']}.yaml")
    )
    template_path = (
        config['nemo_inspector']['prompt_template']
        if os.path.isfile(str(config['nemo_inspector']['prompt_template']))
        else os.path.join(TEMPLATES_FOLDER, f"{config['nemo_inspector']['prompt_template']}.yaml")
    )

    if not os.path.isfile(conf_path) and not os.path.isfile(template_path):
        prompt_config = initialize_default(PromptConfig)
    elif not os.path.isfile(conf_path):
        prompt_config = initialize_default(PromptConfig, load_config(template_path))
    elif not os.path.isfile(template_path):
        prompt_config = initialize_default(PromptConfig, asdict(get_prompt(config_path).config))
    else:
        prompt_config = initialize_default(PromptConfig, asdict(get_prompt(config_path, template_path).config))

    config['nemo_inspector']['prompt'] = asdict(prompt_config)
    update_nested_dict(config['nemo_inspector']['prompt'], OmegaConf.to_container(cfg).get('prompt', {}))

    for separator_type, separator in CODE_SEPARATORS.items():
        if not config['nemo_inspector']['prompt']['template'][separator_type]:
            config['nemo_inspector']['prompt']['template'][separator_type] = separator

    config['nemo_inspector']['inspector_params']['code_separators'] = (
        config['nemo_inspector']['prompt']['template'][CODE_BEGIN],
        config['nemo_inspector']['prompt']['template'][CODE_END],
    )
    config['nemo_inspector']['inspector_params']['code_output_separators'] = (
        config['nemo_inspector']['prompt']['template'][CODE_OUTPUT_BEGIN],
        config['nemo_inspector']['prompt']['template'][CODE_OUTPUT_END],
    )

    config['nemo_inspector']['retrieval_fields'] = get_specific_fields(config['nemo_inspector'], RETRIEVAL_FIELDS)

    config['nemo_inspector']['input_file'] = str(config['nemo_inspector']['input_file'])
    for name in ['offset', 'max_samples', 'batch_size', 'skip_filled', 'dry_run']:
        config['nemo_inspector'].pop(name)


set_config()
server = Flask(__name__)
server.config.update(config)

assets_path = os.path.join(os.path.dirname(__file__), 'assets')

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    server=server,
    assets_folder=assets_path,
)

from callbacks.analyze_callbacks import choose_base_model
from callbacks.base_callback import nav_click
from callbacks.run_prompt_callbacks import preview
