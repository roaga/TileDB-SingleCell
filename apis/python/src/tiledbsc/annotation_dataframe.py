import tiledb
from .tiledb_array import TileDBArray
from .tiledb_group import TileDBGroup
from .soma_options import SOMAOptions
import tiledbsc.util as util

import pandas as pd
import numpy as np

from typing import Optional, Tuple, List


class AnnotationDataFrame(TileDBArray):
    """
    Nominally for `obs` and `var` data within a soma. These have one string dimension, and multiple attributes.
    """

    dim_name: str

    # ----------------------------------------------------------------
    def __init__(
        self,
        uri: str,
        name: str,
        parent: Optional[TileDBGroup] = None,
    ):
        """
        See the TileDBObject constructor.
        """
        assert name in ["obs", "var"]
        super().__init__(uri=uri, name=name, parent=parent)
        self.dim_name = name + "_id"

    # ----------------------------------------------------------------
    def shape(self):
        """
        Returns a tuple with the number of rows and number of columns of the `AnnotationDataFrame`.
        The row-count is the number of obs_ids (for `obs`) or the number of var_ids (for `var`).
        The column-count is the number of columns/attributes in the dataframe.
        """
        with self._open("r") as A:
            # These TileDB arrays are string-dimensioned sparse arrays so there is no '.shape'.
            # Instead we compute it ourselves.  See also:
            # * https://github.com/single-cell-data/TileDB-SingleCell/issues/10
            # * https://github.com/TileDB-Inc/TileDB-Py/pull/1055
            #
            # Also note that this row-count for obs/var is used by the .shape() methods
            # for X, raw.X, obsp, and varp -- see the AssayMatrix.shape method.
            if self.uri.startswith("tiledb://"):
                num_rows = len(
                    A.query(attrs=[], dims=[self.dim_name])[:][self.dim_name].tolist()
                )
            else:
                # This is quicker than the query -- we can use it safely off TileDB Cloud,
                # and if there's just one fragment written.
                fragment_info = tiledb.array_fragments(self.uri, ctx=self._ctx)
                if len(fragment_info) == 1:
                    num_rows = sum(fragment_info.cell_num)
                else:
                    num_rows = len(
                        A.query(attrs=[], dims=[self.dim_name])[:][
                            self.dim_name
                        ].tolist()
                    )
            num_cols = A.schema.nattr
            return (num_rows, num_cols)

    # ----------------------------------------------------------------
    def ids(self) -> List[str]:
        """
        Returns the `obs_ids` in the matrix (for `obs`) or the `var_ids` (for `var`).
        """
        with self._open("r") as A:
            # TileDB string dims are ASCII not UTF-8. Decode them so they readback
            # not like `b"AKR1C3"` but rather like `"AKR1C3"`.
            retval = A.query(attrs=[], dims=[self.dim_name])[:][self.dim_name].tolist()
            return [e.decode() for e in retval]

    # ----------------------------------------------------------------
    def keys(self) -> List[str]:
        """
        Returns the column names for the `obs` or `var` dataframe.  For obs and varp, `.keys()` is a
        keystroke-saver for the more general array-schema accessor `attr_names`.
        """
        return self.attr_names()

    # ----------------------------------------------------------------
    def dim_select(self, ids):
        """
        Selects a slice out of the dataframe with specified `obs_ids` (for `obs`) or `var_ids` (for `var`).
        If `ids` is `None`, the entire dataframe is returned.
        """
        if ids is None:
            with self._open("r") as A:
                df = A.df[:]
        else:
            with self._open("r") as A:
                df = A.df[ids]
        # We do not need this:
        #   df.set_index(self.dim_name, inplace=True)
        # as long as these arrays (for this class) are written using tiledb.from_pandas which
        # sets this metadata:
        #   >>> A.meta.items()
        #   (('__pandas_index_dims', '{"obs_id": "<U0"}'),)
        # so the set_index is already done for us.

        # TODO: when UTF-8 attributes are queryable using TileDB-Py's QueryCondition API we can remove this.
        # This is the 'decode on read' part of our logic; in dim_select we have the 'encode on write' part.
        # Context: https://github.com/single-cell-data/TileDB-SingleCell/issues/99.
        return self._ascii_to_unicode_dataframe_readback(df)

    # ----------------------------------------------------------------
    def df(self, ids=None) -> pd.DataFrame:
        """
        Keystroke-saving alias for `.dim_select()`. If `ids` are provided, they're used
        to subselect; if not, the entire dataframe is returned.
        """
        return self.dim_select(ids)

    # ----------------------------------------------------------------
    # TODO: this is a v1 for prototype/demo timeframe -- needs expanding.
    def attribute_filter(self, query_string, col_names_to_keep):
        """
        Selects from obs/var using a TileDB-Py `QueryCondition` string such as
        `cell_type == "blood"`. Returns None if the slice is empty.
        This is a v1 implementation for the prototype/demo timeframe.
        """
        with self._open() as A:
            qc = tiledb.QueryCondition(query_string)
            slice_query = A.query(attr_cond=qc)
            slice_df = slice_query.df[:][col_names_to_keep]
            nobs = len(slice_df)
            if nobs == 0:
                return None
            else:
                # This is the 'decode on read' part of our logic; in dim_select we have the 'encode on write' part.
                # Context: https://github.com/single-cell-data/TileDB-SingleCell/issues/99.
                return self._ascii_to_unicode_dataframe_readback(slice_df)

    # ----------------------------------------------------------------
    def _ascii_to_unicode_dataframe_readback(self, df):
        """
        Implements the 'decode on read' partof our logic as noted in `dim_select()`.
        """
        for k in df:
            dfk = df[k]
            if len(dfk) > 0 and type(dfk[0]) == bytes:
                df[k] = dfk.map(lambda e: e.decode())
        return df

    # ----------------------------------------------------------------
    def from_dataframe(self, dataframe: pd.DataFrame, extent: int) -> None:
        """
        Populates the `obs` or `var` subgroup for a SOMA object.

        :param dataframe: `anndata.obs`, `anndata.var`, `anndata.raw.var`.
        :param extent: TileDB `extent` parameter for the array schema.
        """

        offsets_filters = tiledb.FilterList(
            [tiledb.PositiveDeltaFilter(), tiledb.ZstdFilter(level=-1)]
        )
        dim_filters = tiledb.FilterList([tiledb.ZstdFilter(level=-1)])
        attr_filters = tiledb.FilterList([tiledb.ZstdFilter(level=-1)])

        if self._verbose:
            s = util.get_start_stamp()
            print(f"{self._indent}START  WRITING {self.uri}")

        # Make the row-names column (barcodes for obs, gene names for var) explicitly named.
        # Otherwise it'll be called '__tiledb_rows'.
        #
        # Before:
        #
        #   >>> anndata.obs
        #                  orig.ident nCount_RNA nFeature_RNA ...
        #   ATGCCAGAACGACT 0          70.0       47           ...
        #   CATGGCCTGTGCAT 0          85.0       52           ...
        #   ...            ...        ...        ...          ...
        #   GGAACACTTCAGAC 0          150.0      30           ...
        #   CTTGATTGATCTTC 0          233.0      76           ...
        #
        # After:
        #
        #   >>> anndata.obs.rename_axis('obs_id')
        #                  orig.ident nCount_RNA nFeature_RNA ...
        #   obs_id
        #   ATGCCAGAACGACT 0          70.0       47           ...
        #   CATGGCCTGTGCAT 0          85.0       52           ...
        #   ...            ...        ...        ...          ...
        #   GGAACACTTCAGAC 0          150.0      30           ...
        #   CTTGATTGATCTTC 0          233.0      76           ...
        dataframe = dataframe.rename_axis(self.dim_name)

        mode = "ingest"
        if self.exists():
            mode = "append"
            if self._verbose:
                print(f"{self._indent}Re-using existing array {self.uri}")

        # ISSUE:
        # TileDB attributes can be stored as Unicode but they are not yet queryable via the TileDB
        # QueryCondition API. While this needs to be addressed -- global collaborators will want to
        # write annotation-dataframe values in Unicode -- until then, to make obs/var data possible
        # to query, we need to store these as ASCII.
        #
        # This is (besides collation) a storage-level issue not a presentation-level issue: At write
        # time, this works — "α,β,γ" stores as "\xce\xb1,\xce\xb2,\xce\xb3"; at read time: since
        # SOMA is an API: utf8-decode those strings when a query is done & give the user back
        # "α,β,γ".
        #
        # CONTEXT:
        # https://github.com/single-cell-data/TileDB-SingleCell/issues/99
        # https://github.com/single-cell-data/TileDB-SingleCell/pull/101
        # https://github.com/single-cell-data/TileDB-SingleCell/issues/106
        # https://github.com/single-cell-data/TileDB-SingleCell/pull/117
        #
        # IMPLEMENTATION:
        # Python types -- float, string, what have you -- appear as dtype('O') which is not useful.
        # Also, `tiledb.from_pandas` has `column_types` but that _forces_ things to string to a
        # particular if they shouldn't be.
        #
        # Instead, we use `dataframe.convert_dtypes` to get a little jump on what `tiledb.from_pandas`
        # is going to be doing anyway, namely, type-inferring to see what is going to be a string.
        #
        # TODO: when UTF-8 attributes are queryable using TileDB-Py's QueryCondition API we can remove this.
        column_types = {}
        for column_name in dataframe.keys():
            dfc = dataframe[column_name]
            if len(dfc) > 0 and type(dfc[0]) == str:
                # Force ASCII storage if string, in order to make obs/var columns queryable.
                column_types[column_name] = np.dtype("S")

        tiledb.from_pandas(
            uri=self.uri,
            dataframe=dataframe,
            name=self.name,
            sparse=True,
            allows_duplicates=False,
            offsets_filters=offsets_filters,
            attr_filters=attr_filters,
            dim_filters=dim_filters,
            capacity=100000,
            tile=extent,
            column_types=column_types,
            ctx=self._ctx,
            mode=mode,
        )

        self._set_soma_object_type_metadata()

        if self._verbose:
            print(util.format_elapsed(s, f"{self._indent}FINISH WRITING {self.uri}"))
