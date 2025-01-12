import tiledb

from .soma_options import SOMAOptions
from .tiledb_group import TileDBGroup
from .uns_array import UnsArray
import tiledbsc.util as util

import anndata as ad
import pandas as pd
import numpy as np
import scipy

from typing import Optional, List, Dict, Union

import os


class UnsGroup(TileDBGroup):
    """
    Nominally for soma uns.
    """

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
        super().__init__(uri=uri, name=name, parent=parent)

    # ----------------------------------------------------------------
    def keys(self):
        """
        For uns, `.keys()` is a keystroke-saver for the more general group-member
        accessor `._get_member_names()`.
        """
        return self._get_member_names()

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
        Returns an `UnsArray` or `UnsGroup` element at the given name within the group, or None if
        no such member exists.  Overloads the [...] operator.
        """

        with self._open("r") as G:
            if not name in G:
                return None

            print("<<", self.uri, ">>", "NAME", name, "TYPE", type(name))

            obj = G[name]  # This returns a tiledb.object.Object.
            if obj.type == tiledb.tiledb.Group:
                return UnsGroup(uri=obj.uri, name=name, parent=self)
            elif obj.type == tiledb.libtiledb.Array:
                return UnsArray(uri=obj.uri, name=name, parent=self)
            else:
                raise Exception(
                    f"Internal error: found uns group element neither subgroup nor array: type is {str(obj.type)}"
                )

    # ----------------------------------------------------------------
    def __contains__(self, name):
        """
        Implements '"namegoeshere" in soma.uns'.
        """
        with self._open("r") as G:
            return name in G

    # ----------------------------------------------------------------
    def __iter__(self) -> List:  # List[Union[UnsGroup, UnsArray]]
        """
        Implements `for element in soma.uns: ...`
        """
        retval = []
        with self._open("r") as G:
            for O in G:  # tiledb.object.Object
                if O.type == tiledb.tiledb.Group:
                    retval.append(UnsGroup(uri=O.uri, name=O.name, parent=self))
                elif O.type == tiledb.libtiledb.Array:
                    retval.append(UnsArray(uri=O.uri, name=O.name, parent=self))
                else:
                    raise Exception(
                        f"Internal error: found uns group element neither subgroup nor array: type is {str(O.type)}"
                    )
        return iter(retval)

    # ----------------------------------------------------------------
    def show(self, display_name="uns"):
        """
        Recursively displays the uns data.
        """
        print()
        print(display_name + ":")
        for k, v in self.metadata().items():
            if not k.startswith("__"):
                print(k + ":", v)
        for e in self:
            element_display_name = display_name + "/" + e.name
            if isinstance(e, UnsGroup):
                e.show(display_name=element_display_name)
            else:
                print(element_display_name + "/")
                with e._open() as A:
                    print(A[:])

        # uns:
        # scalar_float: 3.25
        # scalar_string: a string
        # [1]
        # [ 0.    1.25  2.5   3.75  5.    6.25  7.5   8.75 10.   11.25]
        # [ 0 10 20 30 40 50 60 70 80 90]
        # [1 2 3]
        # [[1. 2. 3.]
        #  [4. 5. 6.]]
        #
        # uns/simple_dict:
        # B: one
        # [0]
        # ['a' 'b' 'c']
        # OrderedDict([('A', array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=int32)), ('__tiledb_rows', array([b'0', b'1', b'2', b'3', b'4', b'5', b'6', b'7', b'8', b'9'],
        #       dtype=object))])
        # ['0' '100' '200' '300' '400' '500' '600' '700' '800' '900']

    # ----------------------------------------------------------------
    def from_anndata_uns(self, uns: ad.compat.OverloadedDict):
        """
        Populates the uns group for the soma object.

        :param uns: anndata.uns.
        """

        if self._verbose:
            s = util.get_start_stamp()
            print(f"{self._indent}START  WRITING {self.uri}")

        # Must be done first, to create the parent directory
        self._create()

        for key in uns.keys():
            component_uri = os.path.join(self.uri, key)
            value = uns[key]

            if key == "rank_genes_groups":
                # TODO:
                # This is of type 'structured array':
                # https://numpy.org/doc/stable/user/basics.rec.html
                #
                # >>> a.uns['rank_genes_groups']['names'].dtype
                # dtype([('0', 'O'), ('1', 'O'), ('2', 'O'), ('3', 'O'), ('4', 'O'), ('5', 'O'), ('6', 'O'), ('7', 'O')])
                # >>> type(a.uns['rank_genes_groups']['names'])
                # <class 'numpy.ndarray'>
                #
                # We don’t have a way to model this directly in TileDB schema right now. We support
                # multiplicities of a single scalar type, e.g. a record array with cell_val_num==3
                # and float32 slots (which would correspond to numpy record array
                # np.dtype([("field1", "f4"), ("field2", "f4"), ("field3", "f4",)])). We don’t
                # support nested cells, AKA "list" type.
                #
                # This could, however, be converted to a dataframe and ingested that way.
                print(f"{self._indent}Skipping structured array:", component_uri)
                continue

            if isinstance(value, (dict, ad.compat.OverloadedDict)):
                # Nested data, e.g. a.uns['draw-graph']['params']['layout']
                subgroup = UnsGroup(uri=component_uri, name=key, parent=self)
                subgroup.from_anndata_uns(value)
                self._add_object(subgroup)
                continue

            # Write scalars as metadata, not length-1 component arrays
            if isinstance(value, np.str_):
                with self._open("w") as G:
                    G.meta[key] = value
                # TODO: WUT
                # Needs explicit cast from numpy.str_ to str for tiledb.from_numpy
                continue

            if isinstance(value, (int, float, str)):
                # Nominally this is unit-test data
                with self._open("w") as G:
                    G.meta[key] = value
                continue

            # Everything else is a component array, or unhandleable
            array = UnsArray(uri=component_uri, name=key, parent=self)

            if isinstance(value, pd.DataFrame):
                array.from_pandas_dataframe(value)
                self._add_object(array)

            elif isinstance(value, scipy.sparse.csr_matrix):
                array.from_scipy_csr(value)
                self._add_object(array)

            elif array._maybe_from_numpyable_object(value):
                self._add_object(array)

            else:
                print(
                    f"{self._indent}Skipping unrecognized type:",
                    component_uri,
                    type(value),
                )

        if self._verbose:
            print(util.format_elapsed(s, f"{self._indent}FINISH WRITING {self.uri}"))

    # ----------------------------------------------------------------
    def to_dict_of_matrices(self) -> Dict:
        """
        Reads the recursive group/array uns data from TileDB storage and returns them as a recursive dict of matrices.
        """
        if not self.exists():
            if self._verbose:
                print(f"{self._indent}{self.uri} not found")
            return {}

        if self._verbose:
            s = util.get_start_stamp()
            print(f"{self._indent}START  read {self.uri}")

        with self._open() as G:
            retval = {}
            for element in G:
                name = os.path.basename(element.uri)  # TODO: update for tiledb cloud

                if element.type == tiledb.tiledb.Group:
                    child_group = UnsGroup(uri=element.uri, name=name, parent=self)
                    retval[name] = child_group.to_dict_of_matrices()

                elif element.type == tiledb.libtiledb.Array:
                    child_array = UnsArray(uri=element.uri, name=name, parent=self)
                    retval[name] = child_array.to_matrix()

                else:
                    raise Exception(
                        f"Internal error: found uns group element neither group nor array: type is {str(element.type)}"
                    )

        if self._verbose:
            print(util.format_elapsed(s, f"{self._indent}FINISH read {self.uri}"))

        return retval
