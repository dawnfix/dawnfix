"""YAML loader that understands CloudFormation short-form tags (!Ref, !Sub, !If, ...).

Each tag becomes its long form ({"Ref": x}, {"Fn::Sub": x}, ...), so a template can be
inspected as plain data without cfn-lint.
"""
import yaml

_FN = ("And", "Base64", "Cidr", "Equals", "FindInMap", "GetAZs", "If", "ImportValue",
       "Join", "Not", "Or", "Select", "Split", "Sub", "Transform", "Length", "ToJsonString")


class CfnLoader(yaml.SafeLoader):
    pass


def _make(name):
    key = "Ref" if name == "Ref" else ("Condition" if name == "Condition" else f"Fn::{name}")

    def construct(loader, node):
        if isinstance(node, yaml.ScalarNode):
            value = loader.construct_scalar(node)
            if name == "GetAtt" and isinstance(value, str):
                value = value.split(".", 1)
        elif isinstance(node, yaml.SequenceNode):
            value = loader.construct_sequence(node, deep=True)
        else:
            value = loader.construct_mapping(node, deep=True)
        return {key: value}
    return construct


for _n in _FN + ("Ref", "GetAtt", "Condition"):
    CfnLoader.add_constructor(f"!{_n}", _make(_n))


def load(path):
    with open(path) as f:
        return yaml.load(f, Loader=CfnLoader)  # noqa: S506 - SafeLoader subclass
