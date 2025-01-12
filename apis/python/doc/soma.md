<a id="tiledbsc.soma"></a>

# tiledbsc.soma

<a id="tiledbsc.soma.SOMA"></a>

## SOMA Objects

```python
class SOMA(TileDBGroup)
```

Single-cell group
Class for representing a group of TileDB groups/arrays that constitute an SOMA ('stack of matrices, annotated')
which includes:

* `X` (`AssayMatrixGroup`): a group of one or more labeled 2D sparse arrays that share the same dimensions.
* `obs` (`AnnotationDataframe`): 1D labeled array with column labels for `X`
* `var` (`AnnotationDataframe`): 1D labeled array with row labels for `X`

Convenience accessors include:

* `soma.obs_keys()` for `soma.obs_names` for `soma.obs.ids()`
* `soma.var_keys()` for `soma.var_names` for `soma.var.ids()`
* `soma.n_obs` for `soma.obs.shape()[0]`
* `soma.n_var` for `soma.var.shape()[0]`

<a id="tiledbsc.soma.SOMA.__init__"></a>

#### \_\_init\_\_

```python
def __init__(uri: str,
             name=None,
             soma_options: Optional[SOMAOptions] = None,
             verbose: Optional[bool] = True,
             config: Optional[tiledb.Config] = None,
             ctx: Optional[tiledb.Ctx] = None,
             parent: Optional[TileDBGroup] = None)
```

Create a new SOMA object. The existing array group is opened at the specified array `uri` if one is present, otherwise a new array group is created.

**Arguments**:

- `uri`: URI of the TileDB group
- `verbose`: Print status messages

<a id="tiledbsc.soma.SOMA.__str__"></a>

#### \_\_str\_\_

```python
def __str__()
```

Implements `print(soma)`.

<a id="tiledbsc.soma.SOMA.__getattr__"></a>

#### \_\_getattr\_\_

```python
def __getattr__(name)
```

This is called on `soma.name` when `name` is not already an attribute.
This is used for `soma.n_obs`, etc.

<a id="tiledbsc.soma.SOMA.obs_keys"></a>

#### obs\_keys

```python
def obs_keys()
```

An alias for `soma.obs.ids()`.

<a id="tiledbsc.soma.SOMA.var_keys"></a>

#### var\_keys

```python
def var_keys()
```

An alias for `soma.var.ids()`.

