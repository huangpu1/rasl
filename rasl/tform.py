# -*- coding: utf-8 -*-
# pylint:disable=invalid-name, too-many-instance-attributes
"""Parameter vector mixin for skimage.transform classes

The constructors for skimage.transforms (which we are substituting for
the MATLAB image library TFORM structures) accept full matrices or
named parameters. Augment them to accept parameter vectors having the
layout of toolbox.parameters_to_projective_matrix(), and to manage
an initial framing transformation.

"""
from __future__ import division, print_function
import copy
import numpy as np
from skimage import transform as tf
from .toolbox import (projective_matrix_to_parameters,
                      parameters_to_projective_matrix)

class ParamvMixin(object):
    """parameter vector mixin for tf.ProjectiveTransform"""

    _ttype = None # override with 'affine', 'similarity', 'projective', etc

    def __init__(self, paramv=None, matrix=None, *args, **kwargs):
        super(ParamvMixin, self).__init__(matrix=matrix, *args, **kwargs)
        self._frame = np.eye(3)
        self._output_shape = None
        if matrix is not None:
            self.matrix = matrix
        elif paramv is not None:
            self.paramv = paramv
        else:
            self.paramv = projective_matrix_to_parameters(
                self._ttype, np.eye(3)) # init with identity transform

    def clone(self, paramv=None):
        """safely copy the tform

        Parameters
        ----------
        paramv : array or None
            If specified, give the new tform this initial parameter settting

        Returns
        -------
        tform : TForm
            a copy of this transform

        """
        cln = copy.copy(self)
        if paramv is None:
            cln.paramv = self.paramv # assignment forces a copy
        else:
            cln.paramv = paramv
        return cln

    @property
    def ttype(self):
        """get the ttype of this transform

        """
        return self._ttype

    @property
    def paramv(self):
        """get the parameter vector of this transform

        """
        return self._paramv

    @paramv.setter
    def paramv(self, paramv):
        """set the parameter vector of this transform

        """
        self._paramv = np.array(paramv, copy=True, dtype=float)
        self._matrix = parameters_to_projective_matrix(self._ttype, paramv)
        self.params = self.frame.dot(self.matrix)

    @property
    def frame(self):
        """get the 3x3 framing matrix of this transform

        """
        return self._frame

    @frame.setter
    def frame(self, frame):
        """set the 3x3 framing matrix of this transform

        """
        self._frame = np.array(frame, copy=True, dtype=float)
        self.params = self.frame.dot(self.matrix)

    @property
    def matrix(self):
        """get the 3x3 projection matrix of this transform

        """
        return self._matrix

    @matrix.setter
    def matrix(self, matrix):
        """set the 3x3 matrix of this transform

        """
        self._matrix = np.array(matrix, copy=True, dtype=float)
        self._paramv = projective_matrix_to_parameters(
            self._ttype, self._matrix)
        self.params = self.frame.dot(self.matrix)

    @property
    def output_shape(self):
        """get output shape of this transform

        """
        return self._output_shape

    def imtransform(self, image, order=3, cval=0, *args, **kwargs):
        """tranform an image, with output image having same shape as input.

        This is implemented as an equivalent to MATLAB's
        imtransform(image, fliptform(tform)), to agree with the
        matrices generated by toolbox.parameters_to_projective_matrix.

        Note 1: It is *backwards* from the usual sense of tf.warp in skimage.

        Note 2: cval is not used during warping. boundaries are filled
        with NaN, and the transformed image has NaNs replaced with
        cval. This avoids made-up data at the expense of eroding
        boundaries.

        """
        # call warp with explicit matrix so we get the optimized behavior
        if not np.all(image == image):
            raise ValueError("NAN given to imtransform"+str(image))
        timage = tf.warp(image, self.params, order=order, mode='constant',
                         cval=np.nan, preserve_range=True,
                         output_shape=self.output_shape, *args, **kwargs)
        if cval == 0:
            timage = np.nan_to_num(timage)
        elif np.isfinite(cval):
            timage = np.where(np.isfinite(timage), timage, cval)
        return timage

    def inset(self, shape, frame, crop=True):
        """configure a framing transformation.

        incorporate a framing transform such that when imtransform is
        applied to an image of the given shape, the image will first
        be inset to the specified interior boundary. This is
        convenient for zooming in on an area of interest prior to
        performing alignment (and an inset of at least 2 is necessary
        to avoid the boundary erosion of a bicubic transform)

        Parameters
        ----------
        shape : tuple
            input image shape
        frame : real or real(2) or (real(2), real(2))
            pixel-width of inset boundary (single number), cropped image
            size (tuple, centered) or boundary points (minimum and
            maximum included points) as pixel offsets into the image,
            ranging [0, max-1]. Negative values are subtracted from
            the dimension size, as with python array indexing.
            NOTE: frame tuples are organized [y,x] (ie, row, col) like all
            other image indexing.
        crop : bool
            if True, the output shape is set to the implied inset frame.
            if False, the inset image will be zoomed to fill the input shape

        """
        shape = np.array(shape, dtype=float)
        bounds = np.array(frame, dtype=float)
        if not bounds.shape:
            # inset a fixed pixel width
            bounds = np.array(((bounds, bounds), (-bounds - 1, -bounds - 1)))
        elif bounds.size == 2:
            # center and crop to size
            inset = (shape - bounds) / 2
            bounds = np.array((np.floor(inset), np.floor(-inset -1)))
        bounds = np.where(bounds < 0, shape + bounds, bounds) # negative idxs
        if crop:
            scale = (1, 1)
            self._output_shape = bounds[1, :] - bounds[0, :] + 1
        else:
            scale = (bounds[1, :] - bounds[0, :]) / (shape - 1)
            self._output_shape = shape
        framemat = parameters_to_projective_matrix(
            # swap x and y indices here
            'affine', [scale[1], 0, bounds[0, 1], 0, scale[0], bounds[0, 0]])
        self.frame = framemat
        return self

class TranslateTransform(ParamvMixin, tf.SimilarityTransform):
    """tf.SimilarityTransform with xy translation only"""
    _ttype = 'translate'

class ScaleTransform(ParamvMixin, tf.SimilarityTransform):
    """tf.SimilarityTransform with scaling only"""
    _ttype = 'scale'

class RotateTransform(ParamvMixin, tf.SimilarityTransform):
    """tf.SimilarityTransform with rotation only"""
    _ttype = 'rotate'

class SimilarityTransform(ParamvMixin, tf.SimilarityTransform):
    """tf.SimilarityTransform with a paramv"""
    _ttype = 'similarity'

class AffineTransform(ParamvMixin, tf.AffineTransform):
    """tf.AffineTransform with a paramv"""
    _ttype = 'affine'

class ProjectiveTransform(ParamvMixin, tf.ProjectiveTransform):
    """tf.ProjectiveTransform with a paramv"""
    _ttype = 'projective'
