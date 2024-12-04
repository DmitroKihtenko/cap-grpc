from logging import getLogger
from typing import Any, Callable

from grpc.aio import ServicerContext

from server.helpers import get_grpc_status_code
from protobuf.types import ProtoType, GRPC_PYTHON_TYPES, SimpleProtoType
from protobuf.definitions import MessageField, PropertyLabel
from server.processors import ProcessingMeta

logger = getLogger(__name__)


def get_enum_value(
    meta: ProcessingMeta,
    field_data: MessageField,
    enum_name: str,
    value: str | None = None,
) -> tuple[str | None, object | None]:
    if field_data.label == PropertyLabel.OPTIONAL and value is None:
        return None, None

    enum_data = meta.object_resolver.summarized_structure.enums[
        enum_name
    ]
    enum_type = meta.object_resolver.get_enum_type(enum_data)
    if field_data.default is not None:
        value = field_data.default
    if value is not None:
        for enum_property in enum_data.fields:
            if value == enum_property.name:
                return enum_property.name, enum_type.Value(enum_property.name)
    return enum_type.keys()[0], enum_type.Value(enum_type.keys()[0])


def get_simple_value(
    field_data: MessageField,
    grpc_type: ProtoType,
    value: Any,
) -> tuple[Any, Any]:
    if field_data.label == PropertyLabel.OPTIONAL and value is None:
        return None, None

    type_data = GRPC_PYTHON_TYPES[grpc_type]
    result = type_data.default_value
    if field_data.default is not None:
        result = field_data.default
    if value is not None:
        if type(value) is type_data.python_type or isinstance(
            value, SimpleProtoType
        ):
            try:
                result = type_data.converter(value)
                if result != value:
                    logger.debug(
                        f"Field '{field_data.name}' converted to "
                        f"corresponding prototype '{grpc_type.value}'"
                    )
            except Exception:
                logger.warning(
                    f"Error converting field '{field_data.name}' to "
                    f"type '{type_data.python_type.__name__}'"
                )
    return result, result


def _fill_object(
    field_data: MessageField,
    value: Any,
    field_name: str | None = None,
) -> dict:
    if field_name is None:
        field_name = field_data.name
    if field_data.is_map and value is None:
        return {}
    if field_data.label == field_data.label.OPTIONAL and value is None:
        return {}
    else:
        return {field_name: value}


def _repeat_if_required(
    field_data: MessageField,
    mock_value: Any,
    inner_message_function: Callable,
    *args,
) -> tuple[list, list]:
    if field_data.label == PropertyLabel.REPEATED:
        raw_values = []
        object_values = []
        if mock_value is None:
            return [], []

        if not isinstance(mock_value, list):
            mock_value = [mock_value]
        for mock_data in mock_value:
            raw_value, object_value = inner_message_function(
                *args, mock_data
            )
            raw_values.append(raw_value)
            object_values.append(object_value)
        return raw_values, object_values
    else:
        return inner_message_function(
            *args, mock_value
        )


def get_kv_message_value(
    meta: ProcessingMeta,
    parent_field: MessageField | None,
    message_name: str,
    mock_value: Any,
) -> tuple[dict | None, dict | None]:
    if mock_value is None:
        return None, None

    message_data = meta.object_resolver.summarized_structure.messages[
        message_name
    ]

    raw_dict = {}
    objects_dict = {}
    if not isinstance(mock_value, dict):
        mock_value = {}

    key_field = message_data.fields[0]
    value_field = message_data.fields[1]

    for property_key, property_value in mock_value.items():
        raw_key, object_key = get_simple_value(
            key_field, key_field.simple_type, property_key,
        )
        if value_field.simple_type == ProtoType.MESSAGE:
            raw_value, object_value = _repeat_if_required(
                value_field,
                property_value,
                get_message_value,
                meta,
                value_field,
                value_field.message_type,
            )
        elif value_field.simple_type == ProtoType.ENUM:
            raw_value, object_value = _repeat_if_required(
                value_field,
                property_value,
                get_enum_value,
                meta,
                value_field,
                value_field.enum_type,
            )
        elif value_field.simple_type == ProtoType.GROUP:
            raw_value, object_value = get_message_value(
                meta,
                value_field,
                value_field.message_type,
                property_value,
            )
        else:
            raw_value, object_value = _repeat_if_required(
                value_field,
                property_value,
                get_simple_value,
                value_field,
                value_field.simple_type,
            )
        raw_dict.update(_fill_object(
            key_field, raw_value, raw_key,
        ))
        objects_dict.update(_fill_object(
            key_field, object_value, object_key
        ))

    return raw_dict, objects_dict

def get_message_value(
    meta: ProcessingMeta,
    parent_field: MessageField | None,
    message_name: str,
    mock_value: Any,
) -> tuple[dict | None, object | None]:
    if (
        parent_field and
        parent_field.label == PropertyLabel.OPTIONAL and
        mock_value is None
    ):
        return None, None

    raw_dict = {}
    objects_dict = {}

    message_data = meta.object_resolver.summarized_structure.messages[
        message_name
    ]
    message_type = meta.object_resolver.get_message_type(message_data)

    if not isinstance(mock_value, dict):
        mock_value = None

    for field_data in message_data.fields:
        mock_property_value = None
        if mock_value is not None:
            mock_property_value = mock_value.get(field_data.name)

        if field_data.simple_type == ProtoType.MESSAGE:
            if field_data.is_map:
                raw_value, object_value = get_kv_message_value(
                    meta,
                    field_data,
                    field_data.message_type,
                    mock_property_value,
                )
            else:
                raw_value, object_value = _repeat_if_required(
                    field_data,
                    mock_property_value,
                    get_message_value,
                    meta,
                    field_data,
                    field_data.message_type,
                )
        elif field_data.simple_type == ProtoType.ENUM:
            raw_value, object_value = _repeat_if_required(
                field_data,
                mock_property_value,
                get_enum_value,
                meta,
                field_data,
                field_data.enum_type,
            )
        elif field_data.simple_type == ProtoType.GROUP:
            raw_value, object_value = get_message_value(
                meta,
                field_data,
                field_data.message_type,
                mock_property_value,
            )
        else:
            raw_value, object_value = _repeat_if_required(
                field_data,
                mock_property_value,
                get_simple_value,
                field_data,
                field_data.simple_type,
            )
        raw_dict.update(_fill_object(
            field_data, raw_value
        ))
        objects_dict.update(_fill_object(
            field_data, object_value
        ))

    return raw_dict, message_type(**objects_dict)


def get_service_message(
    meta: ProcessingMeta,
    message_name: str,
    mock_value: Any,
) -> tuple[dict | None, object | None]:
    raw_value, value = get_message_value(
        meta, None, message_name, mock_value
    )
    if raw_value is None or value is None:
        raw_value, value = {}, {}
    return raw_value, value


async def set_error_data(
    context: ServicerContext,
    meta: ProcessingMeta,
):
    if meta.mock_data.error is None:
        return

    await context.abort(
        get_grpc_status_code(meta.mock_data.error.code),
        meta.mock_data.error.details,
    )


def set_trailing_metadata(
    context: ServicerContext,
    meta: ProcessingMeta,
):
    metadata_list = []
    for key, value in meta.mock_data.trailing_meta.root.items():
        if isinstance(value, list):
            for value_item in value:
                metadata_list.append((key, value_item))
        else:
            metadata_list.append((key, value))
    context.set_trailing_metadata(metadata_list)
