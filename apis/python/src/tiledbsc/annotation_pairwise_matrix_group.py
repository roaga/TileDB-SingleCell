import tiledb
from .soma_options import SOMAOptions
from .tiledb_group import TileDBGroup
from .assay_matrix import AssayMatrix
from .annotation_dataframe import AnnotationDataFrame
import tiledbsc.util as util

import pandas as pd
import scipy

from typing import Optional, Dict, List
import os


class AnnotationPairwiseMatrixGroup(TileDBGroup):
    """
    Nominally for soma obsp and varp. You can find element names using soma.obsp.keys(); you access
    elements using soma.obsp['distances'] etc., or soma.obsp.distances if you prefer.  (The latter
    syntax is possible when the element name doesn't have dashes, dots, etc. in it.)
    """

    row_dim_name: str
    col_dim_name: str
    row_dataframe: AnnotationDataFrame
    col_dataframe: AnnotationDataFrame

    def __init__(
        self,
        uri: str,
        name: str,
        row_dataframe: AnnotationDataFrame,  # Nominally a reference to soma.obs
        col_dataframe: AnnotationDataFrame,  # Nominally a reference to soma.var
        parent: Optional[TileDBGroup] = None,
    ):
        """
        See the `TileDBObject` constructor.
        See `AssayMatrix` for the rationale behind retaining references to the `row_dataframe` and
        `col_dataframe` objects.
        """
        assert name in ["obsp", "varp"]
        super().__init__(uri=uri, name=name, parent=parent)
        if name == "obsp":
            self.row_dim_name = "obs_id_i"
            self.col_dim_name = "obs_id_j"
        else:
            self.row_dim_name = "var_id_i"
            self.col_dim_name = "var_id_j"
        self.row_dataframe = row_dataframe
        self.col_dataframe = col_dataframe

    # ----------------------------------------------------------------
    def keys(self):
        """
        For obsp and varp, `.keys()` is a keystroke-saver for the more general group-member
        accessor `._get_member_names()`.
        """
        return self._get_member_names()

    # ----------------------------------------------------------------
    def __getattr__(self, name):
        """
        This is called on `soma.obsp.name` when `name` is not already an attribute.
        This way you can do `soma.obsp.distances` as an alias for `soma.obsp['distances']`.
        """
        with self._open() as G:
            if not name in G:
                raise AttributeError(
                    f"'{self.__class__.__name__}' object has no attribute '{name}'"
                )
        return self[name]

    # ----------------------------------------------------------------
    def __iter__(self) -> List[AssayMatrix]:
        """
        Implements `for matrix in soma.obsp: ...` and `for matrix in soma.varp: ...`
        """
        retval = []
        for name, uri in self._get_member_names_to_uris().items():
            matrix = AssayMatrix(
                uri=uri,
                name=name,
                row_dim_name=self.row_dim_name,
                col_dim_name=self.col_dim_name,
                row_dataframe=self.row_dataframe,
                col_dataframe=self.col_dataframe,
                parent=self,
            )
            retval.append(matrix)
        return iter(retval)

    # ----------------------------------------------------------------
    def from_matrices_and_dim_values(self, annotation_pairwise_matrices, dim_values):
        """
        Populates the `obsp` or `varp` subgroup for a SOMA object, then writes all the components
        arrays under that group.

        :param annotation_pairwise_matrices: anndata.obsp, anndata.varp, or anndata.raw.varp.
        :param dim_values: anndata.obs_names, anndata.var_names, or anndata.raw.var_names.
        """

        # Must be done first, to create the parent directory
        self._create()
        for matrix_name in annotation_pairwise_matrices.keys():
            anndata_matrix = annotation_pairwise_matrices[matrix_name]
            matrix_uri = os.path.join(self.uri, matrix_name)
            annotation_pairwise_matrix = AssayMatrix(
                uri=matrix_uri,
                name=matrix_name,
                row_dim_name=self.row_dim_name,
                col_dim_name=self.col_dim_name,
                row_dataframe=self.row_dataframe,
                col_dataframe=self.col_dataframe,
                parent=self,
            )
            annotation_pairwise_matrix.from_matrix_and_dim_values(
                anndata_matrix,
                dim_values,
                dim_values,
            )
            self._add_object(annotation_pairwise_matrix)

    # ----------------------------------------------------------------
    def to_dict_of_csr(
        self, obs_df_index, var_df_index
    ) -> Dict[str, scipy.sparse.csr_matrix]:
        """
        Reads the `obsp` or `varp` group-member arrays into a dict from name to member array.
        Member arrays are returned in sparse CSR format.
        """

        grp = None
        try:  # Not all groups have all four of obsm, obsp, varm, and varp.
            grp = tiledb.Group(self.uri, mode="r", ctx=self._ctx)
        except:
            pass
        if grp == None:
            if self._verbose:
                print(f"{self._indent}{self.uri} not found")
            return {}

        if self._verbose:
            s = util.get_start_stamp()
            print(f"{self._indent}START  read {self.uri}")

        matrices_in_group = {}
        for element in self:
            if self._verbose:
                s2 = util.get_start_stamp()
                print(f"{self._indent}START  read {element.uri}")

            matrix_name = os.path.basename(element.uri)  # TODO: fix for tiledb cloud
            matrices_in_group[matrix_name] = element.to_csr_matrix(
                obs_df_index, var_df_index
            )

            if self._verbose:
                print(
                    util.format_elapsed(s2, f"{self._indent}FINISH read {element.uri}")
                )

        grp.close()

        if self._verbose:
            print(util.format_elapsed(s, f"{self._indent}FINISH read {self.uri}"))

        return matrices_in_group

    # At the tiledb-py API level, *all* groups are name-indexable.  But here at the tiledbsc-py
    # level, we implement name-indexing only for some groups:
    #
    # * Most soma member references are done using Python's dot syntax. For example, rather than
    #   soma['X'], we have simply soma.X, and likewise, soma.raw.X.  Likewise soma.obs and soma.var.
    #
    # * Index references are supported for obsm, varm, obsp, varp, and uns. E.g.
    #   soma.obsm['X_pca'] or soma.uns['neighbors']['params']['method']
    #
    # * Overloading the `[]` operator at the TileDBGroup level isn't necessary -- e.g. we don't need
    #   soma['X'] when we have soma.X -- but also it causes circular-import issues in Python.
    #
    # * Rather than doing a TileDBIndexableGroup which overloads the `[]` operator, we overload
    #   the `[]` operator separately in the various classes which need indexing. This is again to
    #   avoid circular-import issues, and means that [] on `AnnotationMatrixGroup` will return an
    #   `AnnotationMatrix, [] on `UnsGroup` will return `UnsArray` or `UnsGroup`, etc.
    def __getitem__(self, name):
        """
        Returns an `AssayMatrix` element at the given name within the group, or `None` if no such
        member exists.  Overloads the `[...]` operator.
        """

        with self._open("r") as G:
            try:
                obj = G[name]  # This returns a tiledb.object.Object.
            except:
                return None

            if obj.type == tiledb.tiledb.Group:
                raise Exception(
                    "Internal error: found group element where array element was expected."
                )
            if obj.type != tiledb.libtiledb.Array:
                raise Exception(
                    f"Internal error: found group element neither subgroup nor array: type is {str(obj.type)}"
                )

            return AssayMatrix(
                uri=obj.uri,
                name=name,
                row_dim_name=self.row_dim_name,
                col_dim_name=self.col_dim_name,
                row_dataframe=self.row_dataframe,
                col_dataframe=self.col_dataframe,
                parent=self,
            )

    def __contains__(self, name):
        """
        Implements `"namegoeshere" in soma.obsp/soma.varp`.
        """
        with self._open("r") as G:
            return name in G
