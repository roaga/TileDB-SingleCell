#!/usr/bin/env python
#!/usr/bin/env python -i

import tiledb
import tiledbsc as t
import sys, os

import anndata
import anndata as ad  # so we can type it either way

import pandas
import pandas as pd  # so we can type it either way
import numpy
import numpy as np  # so we can type it either way
import scipy

from typing import List, Dict

if len(sys.argv) == 1:
    soco_path = "soma-collection"
elif len(sys.argv) == 2:
    soco_path = sys.argv[1]
else:
    print(f"{sys.argv[0]}: need just one soma-collection path.", file=sys.stderr)
    sys.exit(1)

soco = t.SOMACollection(soco_path)

# Interact at the Python prompt now

# ----------------------------------------------------------------
def time_soco_attr_filter_prototype(
    soco: t.SOMACollection,
    obs_attr_name: str,
    obs_query_string: str,
    var_attr_name: str,
    var_query_string: str,
) -> None:

    print()
    print(
        "================================================================ TIME ATTR-FILTER QUERY"
    )
    s = t.util.get_start_stamp()

    # soma.attribute_filter(obs_attr_name="cell_type",obs_query_string='cell_type == "blood"',var_attr_name="feature_name",var_query_string='feature_name == "MT-CO3"')

    soma_slices = []
    for soma in soco:
        soma_slice = soma.attribute_filter(
            obs_attr_name,
            obs_query_string,
            var_attr_name,
            var_query_string,
        )
        if soma_slice != None:
            print()
            print("----------------------------------------------------------------")
            print(soma.uri)
            soma_slice.describe()
            # xxx temp health check: a = soma_slice.to_anndata()
            # xxx temp as another health check try: soma.from_soma_slice()
            print(soma_slice)
            print()

            soma_slices.append(soma_slice)

    print(t.util.format_elapsed(s, f"attr-filter prototype query"))

    result_soma_slice = t.SOMASlice.stack(soma_slices)
    if result_soma_slice is None:
        print("Empty slice")
    else:
        a = result_soma_slice.to_anndata()
        a.write_h5ad("first-light.h5ad")


# ================================================================
time_soco_attr_filter_prototype(
    soco,
    obs_attr_name="cell_type",
    # obs_query_string='cell_type == "pericyte"',
    obs_query_string='tissue == "blood"',
    var_attr_name="feature_name",
    var_query_string='feature_name == "MT-CO3"',
)
