/* inter2d.f -- translated by f2c (version 19991025).
   You must link the resulting object file with the libraries:
	-lf2c -lm   (in that order)
*/

#include "f2c.h"

/* Table of constant values */

static real c_b2 = (float)2.;
static real c_b3 = (float)-1.;
static integer c__0 = 0;
static integer c__1 = 1;
static integer c__15 = 15;
static real c_b25 = (float).001;

doublereal nrievl_(x, y, datain, nxpix, nypix, lendan, intere, scale)
real *x, *y, *datain;
integer *nxpix, *nypix, *lendan, *intere;
real *scale;
{
    /* System generated locals */
    integer datain_dim1, datain_offset, i__1, i__2;
    real ret_val;

    /* Local variables */
    static real xval, yval;
    static integer i__, j;
    static real coeff[361]	/* was [19][19] */, hold21, hold12, hold22, 
	    value;
    extern /* Subroutine */ int wsumr_(), iibip3_(), iibip5_();
    static integer nx, ny;
    static real sx, sy, tx, ty;
    extern /* Subroutine */ int iinisc_();
    static integer rowleh, xindex, yindex, nterms, lastrw, firstw;

/* NRIEVAL -- Procedure to evaluate the 2D interpolant at a given value */
/* of x and y. NRIEVAL allows the interpolation of a few interpolated */
/* points without the computing time and storage required for the */
/* sequential version. The routine assumes that 1 <= x <= nxpix and */
/* 1 <= y <= nypix. */

/* This is a modified version to allow for a stretch factor (the scale */
/* parameter) in the SINC case. */

/* Modifications: Richard Hook, ST-ECF@STScI, December 2003 */

/* This version supports most options, with the exception of SPLINE3. */

/* Richard Hook modified it, September 2002 */
/* Warren Hack, June 2004 */

/*  Used for SPLINE3 option */
/*      integer kx, ky */
/*      real tmp(19*19) */
/* Define common terms */
    /* Parameter adjustments */
    datain_dim1 = *lendan;
    datain_offset = 1 + datain_dim1 * 1;
    datain -= datain_offset;

    /* Function Body */
    nx = (integer) (*x);
    ny = (integer) (*y);
/* Nearest neighbour */
    ret_val = (float)0.;
    if (*intere == 1) {
	ret_val = datain[(integer) (*x + (float).5) + (integer) (*y + (float)
		.5) * datain_dim1];
/* Bilinear */
    } else if (*intere == 2) {
	sx = *x - nx;
	tx = (float)1. - sx;
	sy = *y - ny;
	ty = (float)1. - sy;
	if (nx >= *nxpix) {
	    hold21 = datain[nx + ny * datain_dim1] * (float)2. - datain[nx - 
		    1 + ny * datain_dim1];
	} else {
	    hold21 = datain[nx + 1 + ny * datain_dim1];
	}
	if (ny >= *nypix) {
	    hold12 = datain[nx + ny * datain_dim1] * (float)2. - datain[nx + (
		    ny - 1) * datain_dim1];
	} else {
	    hold12 = datain[nx + (ny + 1) * datain_dim1];
	}
	if (nx >= *nxpix && ny >= *nypix) {
	    hold22 = hold21 * (float)2. - (datain[nx + (ny - 1) * datain_dim1]
		     * (float)2. - datain[nx - 1 + (ny - 1) * datain_dim1]);
	} else if (nx >= *nxpix) {
	    hold22 = hold12 * (float)2. - datain[nx - 1 + (ny + 1) * 
		    datain_dim1];
	} else if (ny >= *nypix) {
	    hold22 = hold21 * (float)2. - datain[nx + 1 + (ny - 1) * 
		    datain_dim1];
	} else {
	    hold22 = datain[nx + 1 + (ny + 1) * datain_dim1];
	}
	value = tx * ty * datain[nx + ny * datain_dim1] + sx * ty * hold21 + 
		sy * tx * hold12 + sx * sy * hold22;
	ret_val = value;
/* Bicubic polynomial: 'poly3' */
    } else if (*intere == 3) {
	rowleh = 19;
	nterms = 4;
	yindex = 1;
/* 	    major problem is that near the edge the interior polynomial */
/* 	    must be defined */

/* 	    use boundary projection to extend the data rows */
	i__1 = ny + 2;
	for (j = ny - 1; j <= i__1; ++j) {
/* 		check that the data row is defined */
	    if (j >= 1 && j <= *nypix) {
/* 		         extend the rows */
		xindex = 1;
		i__2 = nx + 2;
		for (i__ = nx - 1; i__ <= i__2; ++i__) {
		    if (i__ < 1) {
			coeff[xindex + yindex * 19 - 20] = datain[j * 
				datain_dim1 + 1] * (float)2. - datain[2 - i__ 
				+ j * datain_dim1];
		    } else if (i__ > *nxpix) {
			coeff[xindex + yindex * 19 - 20] = datain[*nxpix + j *
				 datain_dim1] * (float)2. - datain[(*nxpix << 
				1) - i__ + j * datain_dim1];
		    } else {
			coeff[xindex + yindex * 19 - 20] = datain[i__ + j * 
				datain_dim1];
		    }
		    ++xindex;
		}
	    } else if (j == ny + 2) {
/* 		         extend the rows */
		xindex = 1;
		i__2 = nx + 2;
		for (i__ = nx - 1; i__ <= i__2; ++i__) {
		    if (i__ < 1) {
			coeff[xindex + yindex * 19 - 20] = datain[(*nypix - 2)
				 * datain_dim1 + 1] * (float)2. - datain[2 - 
				i__ + (*nypix - 2) * datain_dim1];
		    } else if (i__ > *nxpix) {
			coeff[xindex + yindex * 19 - 20] = datain[*nxpix + (*
				nypix - 2) * datain_dim1] * (float)2. - 
				datain[(*nxpix << 1) - i__ + (*nypix - 2) * 
				datain_dim1];
		    } else {
			coeff[xindex + yindex * 19 - 20] = datain[i__ + (*
				nypix - 2) * datain_dim1];
		    }
		    ++xindex;
		}
	    }
	    ++yindex;
	}
/* End of loop over rows (j) */
/* 	 project columns */

/*  awsur -- Weighted sum of 2 real vectors. */
/*           awsur(a,b,c,npix,k1,k2) : c(i) = k1*a(i) + k2*b(i) */
/* Computing MAX */
	i__1 = 1, i__2 = 3 - ny;
	firstw = max(i__1,i__2);
	if (firstw > 1) {
	    i__1 = firstw;
	    for (j = 1; j <= i__1; ++j) {
		wsumr_(&coeff[firstw * 19 - 19], &coeff[((firstw << 1) - j) * 
			19 - 19], &coeff[j * 19 - 19], &nterms, &c_b2, &c_b3);
	    }
	}
/* Computing MIN */
	i__1 = nterms, i__2 = *nypix - ny + 2;
	lastrw = min(i__1,i__2);
	if (lastrw < nterms) {
	    i__1 = nterms - 1;
	    for (j = lastrw + 1; j <= i__1; ++j) {
		wsumr_(&coeff[lastrw * 19 - 19], &coeff[((lastrw << 1) - j) * 
			19 - 19], &coeff[j * 19 - 19], &nterms, &c_b2, &c_b3);
	    }
	} else if (lastrw == 2) {
	    wsumr_(&coeff[lastrw * 19 - 19], &coeff[57], &coeff[57], &nterms, 
		    &c_b2, &c_b3);
	} else {
	    wsumr_(&coeff[lastrw * 19 - 19], &coeff[((lastrw << 1) - 4) * 19 
		    - 19], &coeff[57], &nterms, &c_b2, &c_b3);
	}
/*  center the x value and call evaluation routine */
	xval = *x - nx + 2;
	yval = *y - ny + 2;
	iibip3_(coeff, &c__0, &rowleh, &xval, &yval, &value, &c__1);
	ret_val = value;
/* BIPOLY5 case: 'poly5' */
    } else if (*intere == 4) {
	rowleh = 19;
	nterms = 6;
/* 	     major problem is to define interior polynomial near the edge */

/* 	     loop over the rows of data */
	yindex = 1;
	i__1 = ny + 3;
	for (j = ny - 2; j <= i__1; ++j) {
/* 		select the  rows containing data */
	    if (j >= 1 && j <= *nypix) {
/* 		         extend the rows */
		xindex = 1;
		i__2 = nx + 3;
		for (i__ = nx - 2; i__ <= i__2; ++i__) {
		    if (i__ < 1) {
			coeff[xindex + yindex * 19 - 20] = datain[j * 
				datain_dim1 + 1] * (float)2. - datain[2 - i__ 
				+ j * datain_dim1];
		    } else if (i__ > *nxpix) {
			coeff[xindex + yindex * 19 - 20] = datain[*nxpix + j *
				 datain_dim1] * (float)2. - datain[(*nxpix << 
				1) - i__ + j * datain_dim1];
		    } else {
			coeff[xindex + yindex * 19 - 20] = datain[i__ + j * 
				datain_dim1];
		    }
		    ++xindex;
		}
	    } else if (j == ny + 3) {
/* 		         extend the rows */
		xindex = 1;
		i__2 = nx + 3;
		for (i__ = nx - 2; i__ <= i__2; ++i__) {
		    if (i__ < 1) {
			coeff[xindex + yindex * 19 - 20] = datain[(*nypix - 3)
				 * datain_dim1 + 1] * (float)2. - datain[2 - 
				i__ + (*nypix - 3) * datain_dim1];
		    } else if (i__ > *nxpix) {
			coeff[xindex + yindex * 19 - 20] = datain[*nxpix + (*
				nypix - 3) * datain_dim1] * (float)2. - 
				datain[(*nxpix << 1) - i__ + (*nypix - 3) * 
				datain_dim1];
		    } else {
			coeff[xindex + yindex * 19 - 20] = datain[i__ + (*
				nypix - 3) * datain_dim1];
		    }
		    ++xindex;
		}
	    }
/*     End of loop of 'j' */
	    ++yindex;
	}
/* 	   project columns */
/* Computing MAX */
	i__1 = 1, i__2 = 4 - ny;
	firstw = max(i__1,i__2);
	if (firstw > 1) {
	    i__1 = firstw;
	    for (j = 1; j <= i__1; ++j) {
		wsumr_(&coeff[firstw * 19 - 19], &coeff[((firstw << 1) - j) * 
			19 - 19], &coeff[j * 19 - 19], &nterms, &c_b2, &c_b3);
	    }
	}
/* Computing MIN */
	i__1 = nterms, i__2 = *nypix - ny + 3;
	lastrw = min(i__1,i__2);
	if (lastrw < nterms) {
	    i__1 = nterms - 1;
	    for (j = lastrw + 1; j <= i__1; ++j) {
		wsumr_(&coeff[lastrw * 19 - 19], &coeff[((lastrw << 1) - j) * 
			19 - 19], &coeff[j * 19 - 19], &nterms, &c_b2, &c_b3);
	    }
	} else if (lastrw == 3) {
	    wsumr_(&coeff[lastrw * 19 - 19], &coeff[95], &coeff[95], &nterms, 
		    &c_b2, &c_b3);
	} else {
	    wsumr_(&coeff[lastrw * 19 - 19], &coeff[((lastrw << 1) - 6) * 19 
		    - 19], &coeff[95], &nterms, &c_b2, &c_b3);
	}
/* 	     call evaluation routine */
	xval = *x - nx + 3;
	yval = *y - ny + 3;
	iibip5_(coeff, &c__0, &rowleh, &xval, &yval, &value, &c__1);
	ret_val = value;
/* End of 'poly5' case */

/*  Spline case not implemented due to requirement of 'iispld', */
/*  derived from ii_spline2d.x, to dynamically allocate a working */
/*  array for the computation. */

/*      ELSE IF (INTERE.EQ.5) THEN */
/*         rowleh = 16 + 3 */
/*         ky = 0 */
/*         DO 510 j = ny - 16 /2 + 1, ny + 16 /2 */
/*            if (.not.(j .lt. 1 .or. j .gt. nypix)) THEN */
/*               ky = ky + 1 */
/*                if (ky .eq. 1) THEN */
/*                   yindex = ny - j + 1 */
/*                ENDIF */

/*                kx = 0 */
/*                DO 540 i = nx - 16 /2 + 1, nx + 16 /2 */
/*                   if (.not.(i .lt. 1 .or. i .gt. nxpix)) THEN */
/*                      kx = kx + 1 */
/*                      if (kx .eq. 1) THEN */
/*                         xindex = nx - i + 1 */
/*                      ENDIF */
/*                      coeff(kx+1,ky+1) = datain(i,j) */
/*                   ENDIF */

/* 540            ENDDO */
/*                coeff(1,ky+1) = 0. */
/*                coeff(kx+2,ky+1) = 0. */
/*                coeff(kx+3,ky+1) = 0. */
/*             ENDIF */
/* 510      ENDDO */

/*          call SET1R (0., coeff(1,1), kx+3) */
/*          call SET1R (0., coeff(1,ky+2), kx+3) */
/*          call SET1R (0., coeff(1,ky+3),kx+3) */
/*          call iispld (coeff, tmp, kx, ky+2, rowleh, rowleh) */
/*          call iispld (tmp, coeff, ky, kx+2, rowleh, rowleh) */
/*          xval = xindex + 1 + (x - nx) */
/*          yval = yindex + 1 + (y - ny) */
/*         call iibis3 (coeff, 0, rowleh, xval, yval, value, 1) */
/*         nrievl = (value) */
    } else if (*intere == 6 || *intere == 7) {
	iinisc_(&datain[datain_offset], &c__0, lendan, nypix, x, y, &value, &
		c__1, &c__15, &c_b25, &c_b25, scale);
	ret_val = value;
    }
    return ret_val;
} /* nrievl_ */

