import pcbnew  # type: ignore
import json
import re
import wx  # type: ignore

def get_version():
    bs = pcbnew.GetBuildVersion()
    bs = bs.strip()
    # (6.0.0) -> 6.0.0
    if bs.startswith('(') and bs.endswith(')'):
        bs = re.sub(r'^\(|\)$', '', bs)

    return float('.'.join(bs.split(".")[0:2]))  # e.g. '8.0.0-r3' -> '8.0'

def is_v6():
    version = get_version()
    return version >= 5.99 and version < 6.99

def is_v7():
    version = get_version()
    return version >= 6.99 and version < 7.99

def is_v8():
    version = get_version()
    return version >= 7.99 and version < 8.99

def is_v9():
    version = get_version()
    return version >= 8.99 and version < 9.99

def is_greater_v8():
    return get_version() >= 7.99

def footprint_has_field(footprint, field_name):
    # KiCad 10 replaced the KiCad 8/9 HasFieldByName API with
    # GetFieldText/GetFieldsText. Prefer capability checks over version checks.
    has_field_by_name = getattr(footprint, 'HasFieldByName', None)
    if callable(has_field_by_name):
        return has_field_by_name(field_name)

    get_field_text = getattr(footprint, 'GetFieldText', None)
    if callable(get_field_text):
        try:
            get_field_text(field_name)
            return True
        except (KeyError, RuntimeError):
            return False

    get_fields_text = getattr(footprint, 'GetFieldsText', None)
    if callable(get_fields_text):
        return field_name in get_fields_text()

    has_property = getattr(footprint, 'HasProperty', None)
    return bool(has_property(field_name)) if callable(has_property) else False

def footprint_get_field(footprint, field_name):
    get_field_text = getattr(footprint, 'GetFieldText', None)
    if callable(get_field_text):
        try:
            return get_field_text(field_name)
        except (KeyError, RuntimeError):
            return None

    get_field_by_name = getattr(footprint, 'GetFieldByName', None)
    if callable(get_field_by_name):
        field = get_field_by_name(field_name)
        return field.GetText() if field else None

    get_fields_text = getattr(footprint, 'GetFieldsText', None)
    if callable(get_fields_text):
        return get_fields_text().get(field_name)

    get_property = getattr(footprint, 'GetProperty', None)
    return get_property(field_name) if callable(get_property) else None

def get_mpn_keys():
    keys = [
        'mpn',
        'MPN',
        'Mpn',
        'FAB_MPN',
        'part number',
        'Part Number',
        'Part No.',
        'Mfr. Part No.',
        'Mfg Part',
        'Manufacturer_Part_Number',
    ]
    return keys

def get_pack_keys():
    keys = [
        'pack',
        'PACK',
        'Pack',
        'package',
        'PACKAGE',
        'Package',
        'case',
        'CASE',
        'Case',
    ]
    return keys

def get_dnp_keys():
    keys = [
        'dnp',
        'Dnp',
        'DNp',
        'DNP',
        'dNp',
        'dNP',
        'dnP',
        'DnP',
    ]
    return keys

def get_value_from_footprint_by_keys(fp, keys):
    if not fp or not keys:
        return None
    
    for key in keys:
        if footprint_has_field(fp, key):
            return footprint_get_field(fp, key)

def get_mpn_from_footprint(f):
    return get_value_from_footprint_by_keys(f, get_mpn_keys())

def get_pack_from_footprint(f):
    return get_value_from_footprint_by_keys(f, get_pack_keys())

def get_is_dnp_from_footprint(f):
    for k in get_dnp_keys():
        if footprint_has_field(f, k):
            return True
    return ((f.GetValue().upper() == 'DNP')
            or getattr(f, 'IsDNP', bool)())

def debug_show_object(obj):
    wx.MessageBox(json.dumps(obj))
