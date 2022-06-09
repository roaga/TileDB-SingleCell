import os
from typing import Optional, Union, Dict

import anndata as ad
import numpy as np
import pandas as pd
import pyarrow as pa
import scanpy
import scipy
import tiledb

from tiledbsc import util
from tiledbsc import util_ann

from .soma_options import SOMAOptions
from .tiledb_group import TileDBGroup
from .assay_matrix_group import AssayMatrixGroup
from .annotation_dataframe import AnnotationDataFrame
from .annotation_matrix_group import AnnotationMatrixGroup
from .annotation_pairwise_matrix_group import AnnotationPairwiseMatrixGroup
from .raw_group import RawGroup
from .uns_group import UnsGroup


class SOMASlice(TileDBGroup):
    """
    In-memory-only object for ephemeral extracting out of a SOMA. Can be used to _construct_ a SOMA
    but is not a SOMA (which would entail out-of-memory storage).  Nothing more than a collection of
    pandas.DataFrame objects. No raw or uns.

    XXX is this actually true?

    Note: doing .shape() on any member will not produce the same dimensions as if a SOMA had been
    constructed. For example, soma.obs has num_rows = len(obs_ids) and num_columns = number of dataframe
    attributes. Here, soma_slice.obs has num_columns = TODO
    """

    X: pd.DataFrame
    obs: pd.DataFrame
    var: pd.DataFrame
    obsm: Dict[str, pd.DataFrame]
    varm: Dict[str, pd.DataFrame]
    obsp: Dict[str, pd.DataFrame]
    varp: Dict[str, pd.DataFrame]

    # ----------------------------------------------------------------
    def __init__(
        self,
        X: pd.DataFrame,
        obs: pd.DataFrame,
        var: pd.DataFrame,
        obsm: Optional[Dict[str, pd.DataFrame]] = None,
        varm: Optional[Dict[str, pd.DataFrame]] = None,
        obsp: Optional[Dict[str, pd.DataFrame]] = None,
        varp: Optional[Dict[str, pd.DataFrame]] = None,
    ):
        """
        TODO
        """
        assert isinstance(X, pd.DataFrame)
        assert isinstance(obs, pd.DataFrame)
        assert isinstance(var, pd.DataFrame)

        self.X = X
        self.obs = obs
        self.var = var

        if obsm != None:
            for key, value in obsm.items():
                assert isinstance(value, pd.DataFrame)
            self.obsm = obsm
        else:
            self.obsm = None

        if varm != None:
            for key, value in varm.items():
                assert isinstance(value, pd.DataFrame)
            self.varm = varm
        else:
            self.varm = None

        if obsp != None:
            for key, value in obsp.items():
                assert isinstance(value, pd.DataFrame)
            self.obsp = obsp
        else:
            self.obsp = None

        if varp != None:
            for key, value in varp.items():
                assert isinstance(value, pd.DataFrame)
            self.varp = varp
        else:
            self.varp = None

    # ----------------------------------------------------------------
    def shape(self):
        # obs and var are dataframes: rows are obs_id/var_id; column names vary from
        # one soma/soma-slice to another.
        return (self.obs.shape[0], self.var.shape[0])

    # ----------------------------------------------------------------
    def describe(self):
        print("X", type(self.X), self.X.shape)
        print("OBS", self.obs.shape, type(self.obs))
        print("VAR", self.var.shape, type(self.var))
        if self.obsm != None:
            for key, df in self.obsm.items():
                print("OBSM", key, df.shape, type(df))
        if self.varm != None:
            for key, df in self.varm.items():
                print("VARM", key, df.shape, type(df))
        if self.obsp != None:
            for key, df in self.obsp.items():
                print("OBSP", key, df.shape, type(df))
        if self.varp != None:
            for key, df in self.varp.items():
                print("VARP", key, df.shape, type(df))

    # ----------------------------------------------------------------
    def to_anndata(self) -> ad.AnnData:
        """
        TODO
        """

        self.X.reset_index(inplace=True)  # TODO: COMMENT

        sparseX = util.X_and_ids_to_sparse_matrix(
            self.X,
            # TODO: take from the xdf
            "obs_id",  # row_dim_name: str,
            "var_id",  # col_dim_name: str,
            "value",  # attr_name:    str,
            self.obs.index,
            self.var.index,
        )

        ann = ad.AnnData(
            X=sparseX,
            obs=self.obs,
            var=self.var,
            # TODO: needs logic lie to_dict_of_csr from AMG/APMG
            # obsm=self.obsm,
            # varm=self.varm,
            # obsp=self.obsp,
            # varp=self.varp,
            dtype=sparseX.dtype,
        )

        ann.obs_names_make_unique()
        ann.var_names_make_unique()

        return ann

    # ----------------------------------------------------------------
    @classmethod
    def stack(cls, soma_slices):
        """
        TODO
        """

        if len(soma_slices) == 0:
            return None

        # TODO: extract static method

        # TODO: make obs ids unique
        # # Check obs_ids are unique
        # list_of_obs_ids = []
        # for piece in [list(soma_slice.obs.index) for soma_slice in soma_slices]:
        # list_of_obs_ids += piece
        # set_of_obs_ids = set(list_of_obs_ids)
        # # TODO: informative error message
        # assert len(set_of_obs_ids) == len(list_of_obs_ids)

        # Check column names for each dataframe-type are the same

        # for i, soma_slice in enumerate(soma_slices):
        #     print()
        #     print(soma_slice.X.shape)
        #     print(soma_slice.obs.shape)
        #     print(soma_slice.var.shape)
        #     for key in soma_slice.X.keys():
        #         print(f"slidx={i},df=X,key={key}")
        #     for key in soma_slice.obs.keys():
        #         print(f"slidx={i},df=obs,key={key}")
        #     for key in soma_slice.var.keys():
        #         print(f"slidx={i},df=var,key={key}")
        #     i += 1

        # grep slidx foo \
        # | mlr --d2p sort -f df \
        #   then stats1 -a count -g key,df -f slidx \
        #   then sort -f df -nr slidx_count \
        #   then filter '$slidx_count == 9'
        #
        # key                                df  slidx_count
        # obs_id                             X   9
        # var_id                             X   9
        # value                              X   9
        # assay_ontology_term_id             obs 9
        # sex_ontology_term_id               obs 9
        # is_primary_data                    obs 9
        # organism_ontology_term_id          obs 9
        # disease_ontology_term_id           obs 9
        # ethnicity_ontology_term_id         obs 9
        # development_stage_ontology_term_id obs 9
        # cell_type_ontology_term_id         obs 9
        # tissue_ontology_term_id            obs 9
        # cell_type                          obs 9
        # assay                              obs 9
        # disease                            obs 9
        # organism                           obs 9
        # sex                                obs 9
        # tissue                             obs 9
        # ethnicity                          obs 9
        # development_stage                  obs 9
        # feature_biotype                    var 9
        # feature_is_filtered                var 9
        # feature_name                       var 9
        # feature_reference                  var 9

        slice0 = soma_slices[0]
        for i, slicei in enumerate(soma_slices):
            if i == 0:
                continue
            # This works in Python -- not just a reference/pointer compare but a contents-compare :)
            # TODO: informative error message
            assert list(slicei.X.keys()) == list(slice0.X.keys())
            assert list(slicei.obs.keys()) == list(slice0.obs.keys())
            assert list(slicei.var.keys()) == list(slice0.var.keys())

        result_X_df = pd.concat([soma_slice.X for soma_slice in soma_slices])
        result_obs_df = pd.concat([soma_slice.obs for soma_slice in soma_slices])
        result_var_df = pd.concat([soma_slice.var for soma_slice in soma_slices])

        print("RESULT_X_DF", result_X_df)
        print("RESULT_OBS_DF", result_obs_df)
        print("RESULT_VAR_DF", result_var_df)

        return cls(
            X=result_X_df,
            obs=result_obs_df,
            var=result_var_df,
        )
