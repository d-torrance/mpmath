"""
High-level, mostly calculus-oriented functions.

* Numerical differentiation
* Numerical polynomial operations
* Numerical root-finding
* Numerical integration

etc
"""

from itertools import izip

from settings import (mp, extraprec)
from mptypes import (mpnumeric, mpmathify, mpf, mpc, j, inf, eps,
    AS_POINTS, arange, nstr, nprint, isinf)
from functions import (ldexp, factorial, exp, ln, sin, cos, pi, bernoulli,
    sign)
from gammazeta import int_fac

from quadrature import quad, quadgl, quadts
from matrices import matrix
from linalg import lu_solve

def fsum(*args):
    r"""
    Calculates a sum containing a finite number of terms (for infinite
    series, see :func:`nsum`). You can use either ``fsum(<iterable>)``
    to sum a precomputed sequence of terms, or ``fsum(f, [a,b])`` to
    evaluate `\sum_{k=a}^b f(k)`.

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> fsum([1, 2, 0.5, 7])
        mpf('10.5')
        >>> fsum(lambda k: k**3, [-10, 20])
        mpf('41075.0')

    """
    L = len(args)
    orig = mp.prec
    try:
        mp.prec += 10
        if L == 1:
            v = sum((x for x in args[0]), mpf(0))
        elif L == 2:
            f = args[0]
            a, b = args[1]
            v = sum((f(mpf(k)) for k in xrange(int(a), int(b)+1)), mpf(0))
        else:
            raise ValueError("fsum expected 1 or two arguments")
    finally:
        mp.prec = orig
    return +v

def fprod(*args):
    r"""
    Calculates a product containing a finite number of factors (for
    infinite products, see :func:`nprod`). You can use either
    ``fprod(<iterable>)`` to multiply a precomputed sequence of
    factors, or ``fprod(f, [a,b])`` to evaluate `\prod_{k=a}^b f(k)`.

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> fprod([1, 2, 0.5, 7])
        mpf('7.0')
        >>> fprod(lambda k: k**3, [1, 5])
        mpf('1728000.0')

    """
    L = len(args)
    orig = mp.prec
    try:
        mp.prec += 10
        if L == 1:
            v = mpf(1)
            for p in args[0]:
                v *= p
        elif L == 2:
            f = args[0]
            a, b = args[1]
            v = mpf(1)
            for k in xrange(int(a), int(b)+1):
                v *= f(mpf(k))
        else:
            raise ValueError("fprod expected 1 or two arguments")
    finally:
        mp.prec = orig
    return +v

def richardson(seq):
    r"""
    Given a list ``seq`` of the first `N` elements of a slowly convergent
    infinite sequence, :func:`richardson` computes the `N`-term
    Richardson extrapolate for the limit.

    :func:`richardson` returns `(v, c)` where `v` is the estimated
    limit and `c` is the magnitude of the largest weight used during the
    computation. The weight provides an estimate of the precision
    lost to cancellation. Due to cancellation effects, the sequence must
    be typically be computed at a much higher precision than the target
    accuracy of the extrapolation.

    **Applicability and issues**

    The `N`-step Richardson extrapolation algorithm used by
    :func:`richardson` is described in [1].

    Richardson extrapolation only works for a specific type of sequence,
    namely one converging like partial sums of
    `P(1)/Q(1) + P(2)/Q(2) + \ldots` where `P` and `Q` are polynomials.
    When the sequence does not convergence at such a rate
    :func:`richardson` generally produces garbage.

    Richardson extrapolation has the advantage of being fast: the `N`-term
    extrapolate requires only `O(N)` arithmetic operations, and usually
    produces an estimate that is accurate to `O(N)` digits. Contrast with
    the Shanks transformation (see :func:`shanks`), which requires
    `O(N^2)` operations.

    :func:`richardson` is unable to produce an estimate for the
    approximation error. One way to estimate the error is to perform
    two extrapolations with slightly different `N` and comparing the
    results.

    Richardson extrapolation does not work for oscillating sequences.
    As a simple workaround, :func:`richardson` detects if the last
    three elements do not differ monotonically, and in that case
    applies extrapolation only to the even-index elements.

    **Example**

    Applying Richardson extrapolation to the Leibniz series for `\pi`::

        >>> from mpmath import *
        >>> mp.dps = 30
        >>> S = [4*sum(mpf(-1)**n/(2*n+1) for n in range(m))
        ...     for m in range(1,30)]
        >>> v, c = richardson(S[:10])
        >>> print v
        3.2126984126984126984126984127
        >>> nprint([v-pi, c])
        [7.11058e-2, 2.0]

        >>> v, c = richardson(S[:30])
        >>> print v
        3.14159265468624052829954206226
        >>> nprint([v-pi, c])
        [1.09645e-9, 20833.3]

    **References**

    1. C. M. Bender & S. A. Orszag, "Advanced Mathematical Methods for
       Scientists and Engineers", Springer 1999, pp. 375-376

    """
    assert len(seq) >= 3
    if sign(seq[-1]-seq[-2]) != sign(seq[-2]-seq[-3]):
        seq = seq[::2]
    N = len(seq)//2-1
    s = mpf(0)
    # The general weight is c[k] = (N+k)**N * (-1)**(k+N) / k! / (N-k)!
    # To avoid repeated factorials, we simplify the quotient
    # of successive weights to obtain a recurrence relation
    c = (-1)**N * N**N / mpf(int_fac(N))
    maxc = 1
    for k in xrange(N+1):
        s += c * seq[N+k]
        maxc = max(abs(c), maxc)
        c *= (k-N)*mpf(k+N+1)**N
        c /= ((1+k)*mpf(k+N)**N)
    return s, maxc

def shanks(seq, table=None, randomized=False):
    r"""
    Given a list ``seq`` of the first `N` elements of a slowly
    convergent infinite sequence `(A_k)`, :func:`shanks` computes the iterated
    Shanks transformation `S(A), S(S(A)), \ldots, S^{N/2}(A)`. The Shanks
    transformation often provides strong convergence acceleration,
    especially if the sequence is oscillating.

    The iterated Shanks transformation is computed using the Wynn
    epsilon algorithm (see [1]). :func:`shanks` returns the full
    epsilon table generated by Wynn's algorithm, which can be read
    off as follows:

    * The table is a list of lists forming a lower triangular matrix,
      where higher row and column indices correspond to more accurate
      values.
    * The columns with even index hold dummy entries (required for the
      computation) and the columns with odd index hold the actual
      extrapolates.
    * The last element in the last row is typically the most
      accurate estimate of the limit.
    * The difference to the third last element in the last row
      provides an estimate of the approximation error.
    * The magnitude of the second last element provides an estimate
      of the numerical accuracy lost to cancellation.

    For convenience, so the extrapolation is stopped at an odd index
    so that ``shanks(seq)[-1][-1]`` always gives an estimate of the
    limit.

    Optionally, an existing table can be passed to :func:`shanks`.
    This can be used to efficiently extend a previous computation after
    new elements have been appended to the sequence. The table will
    then be updated in-place.

    **The Shanks transformation**

    The Shanks transformation is defined as follows (see [2]): given
    the input sequence `(A_0, A_1, \ldots)`, the transformed sequence is
    given by

    .. math ::

        S(A_k) = \frac{A_{k+1}A_{k-1}-A_k^2}{A_{k+1}+A_{k-1}-2 A_k}

    The Shanks transformation gives the exact limit `A_{\infty}` in a
    single step if `A_k = A + a q^k`. Note in particular that it
    extrapolates the exact sum of a geometric series in a single step.

    Applying the Shanks transformation once often improves convergence
    substantially for an arbitrary sequence, but the optimal effect is
    obtained by applying it iteratively:
    `S(S(A_k)), S(S(S(A_k))), \ldots`.

    Wynn's epsilon algorithm provides an efficient way to generate
    the table of iterated Shanks transformations. It reduces the
    computation of each element to essentially a single division, at
    the cost of requiring dummy elements in the table. See [1] for
    details.

    **Precision issues**

    Due to cancellation effects, the sequence must be typically be
    computed at a much higher precision than the target accuracy
    of the extrapolation.

    If the Shanks transformation converges to the exact limit (such
    as if the sequence is a geometric series), then a division by
    zero occurs. By default, :func:`shanks` handles this case by
    terminating the iteration and returning the table it has
    generated so far. With *randomized=True*, it will instead
    replace the zero by a pseudorandom number close to zero.
    (TODO: find a better solution to this problem.)

    **Examples**

    We illustrate by applying Shanks transformation to the Leibniz
    series for `\pi`::

        >>> from mpmath import *
        >>> mp.dps = 50
        >>> S = [4*sum(mpf(-1)**n/(2*n+1) for n in range(m))
        ...     for m in range(1,30)]
        >>>
        >>> T = shanks(S[:7])
        >>> for row in T:
        ...     nprint(row)
        ...
        [-0.75]
        [1.25, 3.16667]
        [-1.75, 3.13333, -28.75]
        [2.25, 3.14524, 82.25, 3.14234]
        [-2.75, 3.13968, -177.75, 3.14139, -969.937]
        [3.25, 3.14271, 327.25, 3.14166, 3515.06, 3.14161]

    The extrapolated accuracy is about 4 digits, and about 4 digits
    may have been lost due to cancellation::

        >>> L = T[-1]
        >>> nprint([abs(L[-1] - pi), abs(L[-1] - L[-3]), abs(L[-2])])
        [2.22532e-5, 4.78309e-5, 3515.06]

    Now we extend the computation::

        >>> T = shanks(S[:25], T)
        >>> L = T[-1]
        >>> nprint([abs(L[-1] - pi), abs(L[-1] - L[-3]), abs(L[-2])])
        [3.75527e-19, 1.48478e-19, 2.96014e+17]

    The value for pi is now accurate to 18 digits. About 18 digits may
    also have been lost to cancellation.

    Here is an example with a geometric series, where the convergence
    is immediate (the sum is exactly 1)::

        >>> mp.dps = 15
        >>> for row in shanks([0.5, 0.75, 0.875, 0.9375, 0.96875]):
        ...     nprint(row)
        [4.0]
        [8.0, 1.0]

    **References**

    1. P. R. Graves-Morris, D. E. Roberts, A. Salam, "The epsilon
       algorithm and related topics", Journal of Computational and
       Applied Mathematics, Volume 122, Issue 1-2  (October 2000)

    2. C. M. Bender & S. A. Orszag, "Advanced Mathematical Methods for
       Scientists and Engineers", Springer 1999, pp. 368-375

    """
    assert len(seq) >= 2
    if table:
        START = len(table)
    else:
        START = 0
        table = []
    STOP = len(seq) - 1
    if STOP & 1:
        STOP -= 1
    one = mpf(1)
    if randomized:
        from random import Random
        rnd = Random()
        rnd.seed(START)
    for i in xrange(START, STOP):
        row = []
        for j in xrange(i+1):
            if j == 0:
                a, b = 0, seq[i+1]-seq[i]
            else:
                if j == 1:
                    a = seq[i]
                else:
                    a = table[i-1][j-2]
                b = row[j-1] - table[i-1][j-1]
            if not b:
                if randomized:
                    b = rnd.getrandbits(10)*eps
                elif i & 1:
                    return table[:-1]
                else:
                    return table
            row.append(a + one/b)
        table.append(row)
    return table

def sumem(f, interval, tol=None, reject=10, integral=None,
    adiffs=None, bdiffs=None, verbose=False, error=False):
    r"""
    Uses the Euler-Maclaurin formula to compute an approximation accurate
    to within ``tol`` (which defaults to the present epsilon) of the sum

    .. math ::

        S = \sum_{k=a}^b f(k)

    where `(a,b)` are given by ``interval`` and `a` or `b` may be
    infinite. The approximation is

    .. math ::

        S \sim \int_a^b f(x) \,dx + \frac{f(a)+f(b)}{2} + 
        \sum_{k=1}^{\infty} \frac{B_{2k}}{(2k)!}
        \left(f^{(2k-1)}(b)-f^{(2k-1)}(a)\right).

    The last sum in the Euler-Maclaurin formula is not generally
    convergent (a notable exception is if `f` is a polynomial, in
    which case Euler-Maclaurin actually gives an exact result).

    The summation is stopped as soon as the quotient between two
    consecutive terms falls below *reject*. That is, by default
    (*reject* = 10), the summation is continued as long as each
    term adds at least one decimal.

    Although not convergent, convergence to a given tolerance can
    often be "forced" if `b = \infty` by summing up to `a+N` and then
    applying the Euler-Maclaurin formula to the sum over the range
    `(a+N+1, \ldots, \infty)`. This procedure is implemented by
    :func:`nsum`.

    By default numerical quadrature and differentiation is used.
    If the symbolic values of the integral and endpoint derivatives
    are known, it is more efficient to pass the value of the
    integral explicitly as ``integral`` and the derivatives
    explicitly as ``adiffs`` and ``bdiffs``. The derivatives
    should be given as iterables that yield
    `f(a), f'(a), f''(a), \ldots` (and the equivalent for `b`).

    **Examples**

    Summation of an infinite series, with automatic and symbolic
    integral and derivative values (the second should be much faster)::

        >>> from mpmath import *
        >>> mp.dps = 50
        >>> print sumem(lambda n: 1/n**2, [32, inf])
        0.03174336652030209012658168043874142714132886413417
        >>> I = mpf(1)/32
        >>> D = adiffs=((-1)**n*fac(n+1)*32**(-2-n) for n in xrange(999))
        >>> print sumem(lambda n: 1/n**2, [32, inf], integral=I, adiffs=D)
        0.03174336652030209012658168043874142714132886413417

    An exact evaluation of a finite polynomial sum::

        >>> print sumem(lambda n: n**5-12*n**2+3*n, [-100000, 200000])
        10500155000624963999742499550000.0
        >>> print sum(n**5-12*n**2+3*n for n in xrange(-100000, 200001))
        10500155000624963999742499550000

    """
    tol = tol or +eps
    interval = AS_POINTS(interval)
    a = mpmathify(interval[0])
    b = mpmathify(interval[-1])
    err = mpf(0)
    prev = 0
    M = 10000
    if a == -inf: adiffs = (0 for n in xrange(M))
    else:         adiffs = adiffs or diffs(f, a)
    if b == inf:  bdiffs = (0 for n in xrange(M))
    else:         bdiffs = bdiffs or diffs(f, b)
    orig = mp.prec
    #verbose = 1
    try:
        mp.prec += 10
        s = mpf(0)
        for k, (da, db) in enumerate(izip(adiffs, bdiffs)):
            if k & 1:
                term = (db-da) * bernoulli(k+1) / factorial(k+1)
                mag = abs(term)
                if verbose:
                    print "term", k, "magnitude =", nstr(mag)
                if k > 4 and mag < tol:
                    s += term
                    break
                elif k > 4 and abs(prev) / mag < reject:
                    if verbose:
                        print "Failed to converge"
                    err += mag
                    break
                else:
                    s += term
                prev = term
        # Endpoint correction
        if a != -inf: s += f(a)/2
        if b != inf: s += f(b)/2
        # Tail integral
        if verbose:
            print "Integrating f(x) from x = %s to %s" % (nstr(a), nstr(b))
        if integral:
            s += integral
        else:
            integral, ierr = quad(f, interval, error=True)
            if verbose:
                print "Integration error:", ierr
            s += integral
            err += ierr
    finally:
        mp.prec = orig
    if error:
        return s, err
    else:
        return s

def adaptive_extrapolation(update, emfun, kwargs):
    option = kwargs.get
    tol = option('tol', eps/2**10)
    verbose = option('verbose', False)
    maxterms = option('maxterms', mp.dps*10)
    method = option('method', 'r+s').split('+')
    skip = option('skip', 0)
    steps = iter(option('steps', xrange(10, 10**9, 10)))
    #steps = (10 for i in xrange(1000))
    if method in ('d', 'direct'):
        TRY_RICHARDSON = self.TRY_SHANKS = \
            TRY_EULER_MACLAURIN = False
    else:
        TRY_RICHARDSON = ('r' in method) or ('richardson' in method)
        TRY_SHANKS = ('s' in method) or ('shanks' in method)
        TRY_EULER_MACLAURIN = ('e' in method) or \
            ('euler-maclaurin' in method)

    last_richardson_value = 0
    shanks_table = []
    index = 0
    step = 10
    partial = []
    best = mpf(0)
    orig = mp.prec
    try:
        if TRY_RICHARDSON or TRY_SHANKS:
            mp.prec *= 4
        else:
            mp.prec += 30
        while 1:
            if index >= maxterms:
                break

            # Get new batch of terms
            try:
                step = steps.next()
            except StopIteration:
                pass
            if verbose:
                print "-"*70
                print "Adding terms #%i-#%i" % (index, index+step)
            update(partial, xrange(index, index+step))
            index += step

            # Check direct error
            best = partial[-1]
            error = abs(best - partial[-2])
            if verbose:
                print "Direct error: %s" % nstr(error)
            if error <= tol:
                return best

            # Check each extrapolation method
            if TRY_RICHARDSON:
                value, maxc = richardson(partial)
                # Convergence
                richardson_error = abs(value - last_richardson_value)
                if verbose:
                    print "Richardson error: %s" % \
                        nstr(richardson_error)
                # Convergence
                if richardson_error <= tol:
                    return value
                last_richardson_value = value
                # Unreliable due to cancellation
                if eps*maxc > tol:
                    if verbose:
                        print "Ran out of precision for Richardson"
                    TRY_RICHARDSON = False
                if richardson_error < error:
                    error = richardson_error
                    best = value
            if TRY_SHANKS:
                shanks_table = shanks(partial, shanks_table, randomized=True)
                row = shanks_table[-1]
                if len(row) == 2:
                    est1 = row[-1]
                    shanks_error = 0
                else:
                    est1, maxc, est2 = row[-1], abs(row[-2]), row[-3]
                    shanks_error = abs(est1-est2)
                if verbose:
                    print "Shanks error: %s" % nstr(shanks_error)
                if shanks_error <= tol:
                    return est1
                if eps*maxc > tol:
                    if verbose:
                        print "Ran out of precision for Shanks"
                    TRY_SHANKS = False
                if shanks_error < error:
                    error = shanks_error
                    best = est1
            if TRY_EULER_MACLAURIN:
                if mpc(sign(partial[-1]) / sign(partial[-2])).ae(-1):
                    if verbose:
                        print ("NOT using Euler-Maclaurin: the series appears"
                            " to be alternating, so numerical\n quadrature"
                            " will most likely fail")
                    TRY_EULER_MACLAURIN = False
                else:
                    value, em_error = emfun(index+1, tol)
                    value += partial[-1]
                    if verbose:
                        print "Euler-Maclaurin error: %s" % nstr(em_error)
                    if em_error <= tol:
                        return value
                    if em_error < error:
                        best = value
    finally:
        mp.prec = orig
    if verbose:
        print "Warning: failed to converge to target accuracy"
    return best

def nsum(f, interval, **kwargs):
    r"""
    Computes the sum

    .. math :: S = \sum_{k=a}^b f(k)

    where `(a, b)` = *interval*, and where `a = -\infty` and/or
    `b = \infty` (for finite sums, see :func:`fsum`). Two examples of
    infinite series that can be summed by :func:`nsum`, where the
    first converges rapidly and the second converges slowly, are::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> print nsum(lambda n: 1/fac(n), [0, inf])
        2.71828182845905
        >>> print nsum(lambda n: 1/n**2, [1, inf])
        1.64493406684823

    When possible, :func:`nsum` applies convergence acceleration to
    accurately estimate the sums of slowly convergent series.

    **Options**

    *tol*
        Desired maximum final error. Defaults roughly to the
        epsilon of the working precision.

    *method*
        Which summation algorithm to use (described below).
        Default: ``'richardson+shanks'``.

    *maxterms*
        Cancel after at most this many terms. Default: 10*dps.

    *steps*
        An iterable giving the number of terms to add between
        each extrapolation attempt. The default sequence is
        [10, 20, 30, 40, ...]. For example, if you know that
        approximately 100 terms will be required, efficiency might be
        improved by setting this to [100, 10]. Then the first
        extrapolation will be performed after 100 terms, the second
        after 110, etc.

    *verbose*
        Print details about progress.

    **Methods**

    Unfortunately, an algorithm that can efficiently sum any infinite
    series does not exist. :func:`nsum` implements several different
    algorithms that each work well in different cases. The *method*
    keyword argument selects a method.

    The default method is ``'r+s'``, i.e. both Richardson extrapolation
    and Shanks transformation is attempted. A slower method that
    handles more cases is ``'r+s+e'``. For very high precision
    summation, or if the summation needs to be fast (for example if
    multiple sums need to be evaluated), it is a good idea to
    investigate which one method works best and only use that.

    ``'richardson'`` / ``'r'``:
        Uses Richardson extrapolation. Provides useful extrapolation
        when `f(k) \sim P(k)/Q(k)` or when `f(k) \sim (-1)^k P(k)/Q(k)`
        for polynomials `P` and `Q`. See :func:`richardson` for
        additional information.

    ``'shanks'`` / ``'s'``:
        Uses Shanks transformation. Typically provides useful
        extrapolation when `f(k) \sim c^k` or when successive terms
        alternate signs. Is able to sum some divergent series.
        See :func:`shanks` for additional information.

    ``'euler-maclaurin'`` / ``'e'``:
        Uses the Euler-Maclaurin summation formula to approximate
        the remainder sum by an integral. This requires high-order
        numerical derivatives and numerical integration. The advantage
        of this algorithm is that it works regardless of the
        decay rate of `f`, as long as `f` is sufficiently smooth.
        See :func:`sumem` for additional information.

    ``'direct'`` / ``'d'``:
        Does not perform any extrapolation. This can be used
        (and should only be used for) rapidly convergent series.
        The summation automatically stops when the terms
        decrease below the target tolerance.

    **Basic examples**

    Summation of a series going to negative infinity and a doubly
    infinite series::

        >>> print nsum(lambda k: 1/k**2, [-inf, -1])
        1.64493406684823
        >>> print nsum(lambda k: 1/(1+k**2), [-inf, inf])
        3.15334809493716

    :func:`nsum` handles sums of complex numbers::

        >>> print nsum(lambda k: (0.5+0.25j)**k, [0, inf])
        (1.6 + 0.8j)

    The following sum converges very rapidly, so it is most
    efficient to sum it by disabling convergence acceleration::

        >>> mp.dps = 1000
        >>> a = nsum(lambda k: -(-1)**k * k**2 / fac(2*k), [1, inf],
        ...     method='direct')
        >>> b = (cos(1)+sin(1))/4
        >>> abs(a-b) < mpf('1e-998')
        True

    **Examples with Richardson extrapolation**

    Richardson extrapolation works well for sums over rational
    functions, as well as their alternating counterparts::

        >>> mp.dps = 50
        >>> print nsum(lambda k: 1 / k**3, [1, inf],
        ...     method='richardson')
        1.2020569031595942853997381615114499907649862923405
        >>> print zeta(3)
        1.2020569031595942853997381615114499907649862923405

        >>> print nsum(lambda n: (n + 3)/(n**3 + n**2), [1, inf],
        ...     method='richardson')
        2.9348022005446793094172454999380755676568497036204
        >>> print pi**2/2-2
        2.9348022005446793094172454999380755676568497036204

        >>> print nsum(lambda k: (-1)**k / k**3, [1, inf],
        ...     method='richardson')
        -0.90154267736969571404980362113358749307373971925537
        >>> print -3*zeta(3)/4
        -0.90154267736969571404980362113358749307373971925538

    **Examples with Shanks transformation**

    The Shanks transformation works well for geometric series
    and typically provides excellent acceleration for Taylor
    series near the border of their disk of convergence.
    Here we apply it to a series for `\log(2)`, which can be
    seen as the Taylor series for `\log(1+x)` with `x = 1`::

        >>> print nsum(lambda k: -(-1)**k/k, [1, inf],
        ...     method='shanks')
        0.69314718055994530941723212145817656807550013436025
        >>> print log(2)
        0.69314718055994530941723212145817656807550013436025

    Here we apply it to a slowly convergent geometric series::

        >>> print nsum(lambda k: mpf('0.995')**k, [0, inf],
        ...     method='shanks')
        200.0

    Finally, Shanks' method works very well for alternating series
    where `f(k) = (-1)^k g(k)`, and often does so regardless of
    the exact decay rate of `g(k)`::

        >>> mp.dps = 15
        >>> print nsum(lambda k: (-1)**(k+1) / k**1.5, [1, inf],
        ...     method='shanks')
        0.765147024625408
        >>> print (2-sqrt(2))*zeta(1.5)/2
        0.765147024625408

    The following slowly convergent alternating series has no known
    closed-form value. Evaluating the sum a second time at higher
    precision indicates that the value is probably correct::

        >>> print nsum(lambda k: (-1)**k / log(k), [2, inf],
        ...     method='shanks')
        0.924299897222939
        >>> mp.dps = 30
        >>> print nsum(lambda k: (-1)**k / log(k), [2, inf],
        ...     method='shanks')
        0.92429989722293885595957018136

    **Examples with Euler-Maclaurin summation**

    The sum in the following example has the wrong rate of convergence
    for either Richardson or Shanks to be effective.

        >>> f = lambda k: log(k)/k**2.5
        >>> mp.dps = 15
        >>> print nsum(f, [1, inf], method='euler-maclaurin')
        0.38734195032621
        >>> print -diff(zeta, 2.5)
        0.38734195032621

    Increasing ``steps`` improves speed at higher precision::

        >>> mp.dps = 50
        >>> print nsum(f, [1, inf], method='euler-maclaurin', steps=[250])
        0.38734195032620997271199237593105101319948228874688
        >>> print -diff(zeta, 2.5)
        0.38734195032620997271199237593105101319948228874688

    **Divergent series**

    The Shanks transformation is able to sum some *divergent*
    series. In particular, it is often able to sum Taylor series
    beyond their radius of convergence (this is due to a relation
    between the Shanks transformation and Pade approximations;
    see :func:`pade` for an alternative way to evaluate divergent
    Taylor series).

    Here we apply it to `\log(1+x)` far outside the region of
    convergence::

        >>> mp.dps = 50
        >>> print nsum(lambda k: -(-9)**k/k, [1, inf],
        ...     method='shanks')
        2.3025850929940456840179914546843642076011014886288
        >>> print log(10)
        2.3025850929940456840179914546843642076011014886288

    A particular type of divergent series that can be summed
    using the Shanks transformation is geometric series.
    The result is the same as using the closed-form formula
    for an infinite geometric series::

        >>> mp.dps = 15
        >>> for n in arange(-8, 8):
        ...     if n == 1:
        ...         continue
        ...     print n, 1/(1-n), nsum(lambda k: n**k, [0, inf],
        ...         method='shanks')
        ...
        -8.0 0.111111111111111 0.111111111111111
        -7.0 0.125 0.125
        -6.0 0.142857142857143 0.142857142857143
        -5.0 0.166666666666667 0.166666666666667
        -4.0 0.2 0.2
        -3.0 0.25 0.25
        -2.0 0.333333333333333 0.333333333333333
        -1.0 0.5 0.5
        0.0 1.0 1.0
        2.0 -1.0 -1.0
        3.0 -0.5 -0.5
        4.0 -0.333333333333333 -0.333333333333333
        5.0 -0.25 -0.25
        6.0 -0.2 -0.2
        7.0 -0.166666666666667 -0.166666666666667

    """
    a, b = AS_POINTS(interval)
    if a == -inf:
        if b == inf:
            return f(0) + nsum(lambda k: f(-k) + f(k), [1, inf], **kwargs)
        return nsum(f, [-b, inf], **kwargs)
    elif b != inf:
        raise NotImplementedError("finite sums")

    a = int(a)

    def update(partial_sums, indices):
        if partial_sums:
            psum = partial_sums[-1]
        else:
            psum = mpf(0)
        for k in indices:
            psum = psum + f(a + mpf(k))
            partial_sums.append(psum)

    prec = mp.prec

    def emfun(point, tol):
        workprec = mp.prec
        mp.prec = prec + 10
        v = sumem(f, [point, inf], tol, error=1)
        mp.prec = workprec
        return v

    return +adaptive_extrapolation(update, emfun, kwargs)

def nprod(f, interval, **kwargs):
    """
    Computes the product

    .. math :: P = \prod_{k=a}^b f(k)

    where `(a, b)` = *interval*, and where `a = -\infty` and/or
    `b = \infty`. 

    This function is essentially equivalent to applying :func:`nsum`
    to the logarithm of the product (which, of course, becomes a
    series). All keyword arguments passed to :func:`nprod` are
    forwarded verbatim to :func:`nsum`.

    **Examples**

    A large number of infinite products have known exact values,
    and can therefore be used as a reference. Most of the following
    examples are taken from MathWorld [1].

    First, here are a few infinite products with simple values::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> print 2*nprod(lambda k: (4*k**2)/(4*k**2-1), [1, inf])
        3.14159265358979
        >>> print nprod(lambda k: (1+1/k)**2/(1+2/k), [1, inf])
        2.0
        >>> print nprod(lambda k: (k**3-1)/(k**3+1), [2, inf])
        0.666666666666667
        >>> print nprod(lambda k: (1-1/k**2), [2, inf])
        0.5

    Next, several more infinite products with more complicated
    values::

        >>> print nprod(lambda k: exp(1/k**2), [1, inf])
        5.18066831789712
        >>> print exp(pi**2/6)
        5.18066831789712

        >>> print nprod(lambda k: (k**2-1)/(k**2+1), [2, inf])
        0.272029054982133
        >>> print pi*csch(pi)
        0.272029054982133

        >>> print nprod(lambda k: (k**4-1)/(k**4+1), [2, inf])
        0.8480540493529
        >>> print pi*sinh(pi)/(cosh(sqrt(2)*pi)-cos(sqrt(2)*pi))
        0.8480540493529

        >>> print nprod(lambda k: (1+1/k+1/k**2)**2/(1+2/k+3/k**2), [1, inf])
        1.84893618285824
        >>> print 3*sqrt(2)*cosh(pi*sqrt(3)/2)**2*csch(pi*sqrt(2))/pi
        1.84893618285824

        >>> print nprod(lambda k: (1-1/k**4), [2, inf])
        0.919019477593744
        >>> print sinh(pi)/(4*pi)
        0.919019477593744

        >>> print nprod(lambda k: (1-1/k**6), [2, inf])
        0.982684277742192
        >>> print (1+cosh(pi*sqrt(3)))/(12*pi**2)
        0.982684277742192

        >>> print nprod(lambda k: (1+1/k**2), [2, inf])
        1.83803895518749
        >>> print sinh(pi)/(2*pi)
        1.83803895518749

        >>> print nprod(lambda n: (1+1/n)**n * exp(1/(2*n)-1), [1, inf])
        1.44725592689037
        >>> print exp(1+euler/2)/sqrt(2*pi)
        1.44725592689037

    The following two products are equivalent and can be evaluated in
    terms of a Jacobi theta function. Pi can be replaced by any value
    (as long as convergence is preserved)::

        >>> print nprod(lambda k: (1-pi**-k)/(1+pi**-k), [1, inf])
        0.383845120748167
        >>> print nprod(lambda k: tanh(k*log(pi)/2), [1, inf])
        0.383845120748167
        >>> print jtheta(4,0,1/pi)
        0.383845120748167

    This product does not have a known closed form value::

        >>> print nprod(lambda k: (1-1/2**k), [1, inf])
        0.288788095086602

    **References**

    1. E. W. Weisstein, "Infinite Product",
       http://mathworld.wolfram.com/InfiniteProduct.html,
       MathWorld

    """
    orig = mp.prec
    try:
        # TODO: we are evaluating log(1+eps) -> eps, which is
        # inaccurate. This currently works because nsum greatly
        # increases the working precision. But we should be
        # more intelligent and handle the precision here.
        mp.prec += 10
        v = nsum(lambda n: ln(f(n)), interval, **kwargs)
    finally:
        mp.prec = orig
    return +exp(v)

def limit(f, x, direction=1, exp=False, **kwargs):
    r"""
    Computes an estimate of the limit

    .. math ::

        \lim_{t \to x} f(t)

    where `x` may be finite or infinite.

    For finite `x`, :func:`limit` evaluates `f(x + d/n)` for
    consecutive integer values of `n`, where the approach direction
    `d` may be specified using the *direction* keyword argument.
    For infinite `x`, :func:`limit` evaluates values of
    `f(\mathrm{sign}(x) \cdot n)`.

    If the approach to the limit is not sufficiently fast to give
    an accurate estimate directly, :func:`limit` attempts to find
    the limit using Richardson extrapolation or the Shanks
    transformation. You can select between these methods using
    the *method* keyword (see documentation of :func:`nsum` for
    more information).

    **Options**

    The following options are available with essentially the
    same meaning as for :func:`nsum`: *tol*, *method*, *maxterms*,
    *steps*, *verbose*.

    If the option *exp=True* is set, `f` will be
    sampled at exponentially spaced points `n = 2^1, 2^2, 2^3, \ldots`
    instead of the linearly spaced points `n = 1, 2, 3, \ldots`.
    This can sometimes improve the rate of convergence so that
    :func:`limit` may return a more accurate answer (and faster).
    However, do note that this can only be used if `f`
    supports fast and accurate evaluation for arguments that
    are extremely close to the limit point (or if infinite,
    very large arguments).

    **Examples**

    A basic evaluation of a removable singularity::

        >>> from mpmath import *
        >>> mp.dps = 30
        >>> print limit(lambda x: (x-sin(x))/x**3, 0)
        0.166666666666666666666666666667

    Computing the exponential function using its limit definition::

        >>> print limit(lambda n: (1+3/n)**n, inf)
        20.0855369231876677409285296546
        >>> print exp(3)
        20.0855369231876677409285296546

    A limit for `\pi`::

        >>> f = lambda n: 2**(4*n+1)*fac(n)**4/(2*n+1)/fac(2*n)**2
        >>> print limit(f, inf)
        3.14159265358979323846264338328

    Calculating the coefficient in Stirling's formula::

        >>> print limit(lambda n: fac(n) / (sqrt(n)*(n/e)**n), inf)
        2.50662827463100050241576528481
        >>> print sqrt(2*pi)
        2.50662827463100050241576528481

    Evaluating Euler's constant `\gamma` using the limit representation

    .. math ::

        \gamma = \lim_{n \rightarrow \infty } \left[ \left( 
        \sum_{k=1}^n \frac{1}{k} \right) - \log(n) \right]

    (which converges notoriously slowly)::

        >>> f = lambda n: sum([mpf(1)/k for k in range(1,n+1)]) - log(n)
        >>> print limit(f, inf)
        0.577215664901532860606512090082
        >>> print euler
        0.577215664901532860606512090082

    With default settings, the following limit converges too slowly
    to be evaluated accurately. Changing to exponential sampling
    however gives a perfect result::

        >>> f = lambda x: sqrt(x**3+x**2)/(sqrt(x**3)+x)
        >>> print limit(f, inf)
        0.992518488562331431132360378669
        >>> print limit(f, inf, exp=True)
        1.0

    """

    if isinf(x):
        direction = sign(x)
        g = lambda k: f(mpf(k+1)*direction)
    else:
        direction *= mpf(1)
        g = lambda k: f(x + direction/(k+1))
    if exp:
        h = g
        g = lambda k: h(2**k)

    def update(values, indices):
        for k in indices:
            values.append(g(k+1))

    # XXX: steps used by nsum don't work well
    if not 'steps' in kwargs:
        kwargs['steps'] = [10]

    return +adaptive_extrapolation(update, None, kwargs)


#----------------------------------------------------------------------------#
#                                Differentiation                             #
#----------------------------------------------------------------------------#

def difference_delta(s, n):
    r"""
    Given a sequence `(s_k)` containing at least `n+1` items, returns the
    `n`-th forward difference,

    .. math ::

        \Delta^n = \sum_{k=0}^{\infty} (-1)^{k+n} {n \choose k} s_k.
    """
    d = mpf(0)
    b = (-1) ** (n & 1)
    for k in xrange(n+1):
        d += b * s[k]
        b = (b * (k-n)) // (k+1)
    return d

def diff(f, x, n=1, method='step', scale=1, direction=0):
    r"""
    Numerically computes the derivative of f(x). Optionally, computes
    the nth derivative f^(n)(x), for any order n.

    **Basic examples**

    Derivatives of a simple function::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> print diff(lambda x: x**2 + x, 1.0)
        3.0
        >>> print diff(lambda x: x**2 + x, 1.0, 2)
        2.0
        >>> print diff(lambda x: x**2 + x, 1.0, 3)
        0.0

    The exponential function is invariant under differentiation::

        >>> nprint([diff(exp, 3, n) for n in range(5)])
        [20.0855, 20.0855, 20.0855, 20.0855, 20.0855]

    **Method**

    One of two differentiation algorithms can be chosen with the
    ``method`` keyword argument. The two options are ``'step'``,
    and ``'quad'``. The default method is ``'step'``.

    ``'step'``:

        The derivative is computed using a finite difference
        approximation, with a small step h. This requires n+1 function
        evaluations and must be performed at (n+1) times the target
        precison. Accordingly, f must support fast evaluation at high
        precision.

    ``'quad'``:

        The derivative is computed using complex
        numerical integration. This requires a larger number of function
        evaluations, but the advantage is that not much extra precision
        is required. For high order derivatives, this method may thus
        be faster if f is very expensive to evaluate at high precision.

    With ``'quad'`` the result is likely to have a small imaginary
    component even if the derivative is actually real::

        >>> print diff(sqrt, 1, method='quad')
        (0.5 - 7.58129703509927e-27j)

    **Scale**

    The scale option specifies the scale of variation of f. The step
    size in the finite difference is taken to be approximately
    eps*scale. Thus, for example if f(x) = cos(1000*x), the scale
    should be set to 1/1000 and if f(x) = cos(x/1000), the scale
    should be 1000. By default, scale = 1.

    (In practice, the default scale will work even for cos(1000*x) or
    cos(x/1000). Changing this parameter is a good idea if the scale
    is something *preposterous*.)

    If numerical integration is used, the radius of integration is
    taken to be equal to scale/2. Note that f must not have any
    singularities within the circle of radius scale/2 centered around
    x. If possible, a larger scale value is preferable because it
    typically makes the integration faster and more accurate.

    **Direction**


    By default, :func:`diff` uses a central difference approximation.
    This corresponds to direction=0. Alternatively, it can compute a
    left difference (direction=-1) or right difference (direction=1).
    This is useful for computing left- or right-sided derivatives
    of nonsmooth functions:

        >>> print diff(abs, 0, direction=0)
        0.0
        >>> print diff(abs, 0, direction=1)
        1.0
        >>> print diff(abs, 0, direction=-1)
        -1.0

    More generally, if the direction is nonzero, a right difference
    is computed where the step size is multiplied by sign(direction).
    For example, with direction=+j, the derivative from the positive
    imaginary direction will be computed.

    This option only makes sense with method='step'. If integration
    is used, it is assumed that f is analytic, implying that the
    derivative is the same in all directions.

    """
    if n == 0:
        return f(x)
    orig = mp.prec
    try:
        if method == 'step':
            mp.prec = (orig+20) * (n+1)
            h = ldexp(scale, -orig-10)
            # Applying the finite difference formula recursively n times,
            # we get a step sum weighted by a row of binomial coefficients
            # Directed: steps x, x+h, ... x+n*h
            if direction:
                h *= sign(direction)
                steps = xrange(n+1)
                norm = h**n
            # Central: steps x-n*h, x-(n-2)*h ..., x, ..., x+(n-2)*h, x+n*h
            else:
                steps = xrange(-n, n+1, 2)
                norm = (2*h)**n
            v = difference_delta([f(x+k*h) for k in steps], n)
            v = v / norm
        elif method == 'quad':
            mp.prec += 10
            radius = mpf(scale)/2
            def g(t):
                rei = radius*exp(j*t)
                z = x + rei
                return f(z) / rei**n
            d = quadts(g, [0, 2*pi])
            v = d * factorial(n) / (2*pi)
        else:
            raise ValueError("unknown method: %r" % method)
    finally:
        mp.prec = orig
    return +v

def diffs(f, x, n=inf, method='step', scale=1, direction=0):
    r"""
    Returns a generator that yields the sequence of derivatives

    .. math ::

        f(x), f'(x), f''(x), \ldots, f^{(k)}(x), \ldots

    With ``method='step'``, :func:`diffs` uses only `O(k)`
    function evaluations to generate the first `k` derivatives,
    rather than the roughly `O(k^2)` evaluations
    required if one calls :func:`diff` `k` separate times.

    With `n < \infty`, the generator stops as soon as the
    `n`-th derivative has been generated. If the exact number of
    needed derivatives is known in advance, this is further
    slightly more efficient.

    **Examples**

        >>> nprint(list(diffs(cos, 1, 5)))
        [0.540302, -0.841471, -0.540302, 0.841471, 0.540302, -0.841471]
        >>> for i, d in zip(range(6), diffs(cos, 1)): print i, d
        ...
        0 0.54030230586814
        1 -0.841470984807897
        2 -0.54030230586814
        3 0.841470984807897
        4 0.54030230586814
        5 -0.841470984807897

    """
    if method != 'step':
        k = 0
        while k < n:
            yield diff(f, x, k)
            k += 1
        return

    targetprec = mp.prec

    def getvalues(m):
        callprec = mp.prec
        try:
            mp.prec = workprec = (targetprec+20) * (m+1)
            h = ldexp(scale, -targetprec-10)
            if direction:
                h *= sign(direction)
                y = [f(x+h*k) for k in xrange(m+1)]
                hnorm = h
            else:
                y = [f(x+h*k) for k in xrange(-m, m+1, 2)]
                hnorm = 2*h
            return y, hnorm, workprec
        finally:
            mp.prec = callprec

    yield f(x)
    if n < 1:
        return

    if n is inf:
        A, B = 1, 2
    else:
        A, B = 1, n+1

    while 1:
        y, hnorm, workprec = getvalues(B)
        for k in xrange(A, B):
            try:
                callprec = mp.prec
                mp.prec = workprec
                d = difference_delta(y, k) / hnorm**k
            finally:
                mp.prec = callprec
            yield +d
            if k >= n:
                return
        A, B = B, int(A*1.4+1)
        B = min(B, n)

def diffun(f, n=1, **options):
    """
    Given a function f, returns a function g(x) that evaluates the nth
    derivative f^(n)(x)::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> cos2 = diffun(sin)
        >>> sin2 = diffun(sin, 4)
        >>> print cos(1.3), cos2(1.3)
        0.267498828624587 0.267498828624587
        >>> print sin(1.3), sin2(1.3)
        0.963558185417193 0.963558185417193

    The function f must support arbitrary precision evaluation.
    See :func:`diff` for additional details and supported
    keyword options.
    """
    if n == 0:
        return f
    def g(x):
        return diff(f, x, n, **options)
    return g

def taylor(f, x, n, **options):
    """
    Produce a degree-n Taylor polynomial around the point x of the
    given function f. The coefficients are returned as a list.

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> nprint(chop(taylor(sin, 0, 5)))
        [0.0, 1.0, 0.0, -0.166667, 0.0, 8.33333e-3]

    The coefficients are computed using high-order numerical
    differentiation. The function must be possible to evaluate
    to arbitrary precision. See :func:`diff` for additional details
    and supported keyword options.

    Note that to evaluate the Taylor polynomial as an approximation
    of f, e.g. with polyval, the coefficients must be reversed, and
    the point of the Taylor expansion must be subtracted from
    the argument:

        >>> p = taylor(exp, 2.0, 10)
        >>> print polyval(p[::-1], 2.5 - 2.0)
        12.1824939606092
        >>> print exp(2.5)
        12.1824939607035

    """
    return [d/factorial(i) for i, d in enumerate(diffs(f, x, n, **options))]

def pade(a, L, M):
    """
    Produce the polynomials coefficients p, q from the Taylor 
    coefficients a; p has L+1 coefficients, q has M+1 coefficients,
    with q[0] = 1; a must provide L+M+1 Taylor coefficients.

    Defining::

        P = sum(p[i]*x**i, 0, L), Q = sum(q[i]*x**i, 0, M), 

        A = sum(a[i]*x**i, 0,L+M),

        A(x)*Q(x) = P(x) + O(x**(L+M+1))

    P(x)/Q(x) can provide a good approximation to an analytic function
    beyond the radius of convergence of its Taylor series (example
    from G.A. Baker 'Essentials of Pade Approximants' Academic Press,
    Ch.1A)::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> one = mpf(1)
        >>> def f(x):
        ...   return sqrt((one + 2*x)/(one + x))
        ...
        >>> a = taylor(f, 0, 6)
        >>> p, q = pade(a, 3, 3)
        >>> x = 10
        >>> polyval(p[::-1], x)/polyval(q[::-1], x)
        mpf('1.3816910556680551')
        >>> f(x)
        mpf('1.3816985594155149')
    """
    # To determine L+1 coefficients of P and M coefficients of Q
    # L+M+1 coefficients of A must be provided
    assert(len(a) >= L+M+1)

    if M == 0:
        if L == 0:
            return [mpf(1)], [mpf(1)]
        else:
            return a[:L+1], [mpf(1)]

    # Solve first
    # a[L]*q[1] + ... + a[L-M+1]*q[M] = -a[L+1]
    # ...
    # a[L+M-1]*q[1] + ... + a[L]*q[M] = -a[L+M]    
    A = matrix(M)
    for j in range(M):
        for i in range(min(M, L+j+1)):
            A[j, i] = a[L+j-i]
    v = -matrix(a[(L+1):(L+M+1)])
    x = lu_solve(A, v)
    q = [mpf(1)] + list(x)
    # compute p
    p = [0]*(L+1)
    for i in range(L+1):
        s = a[i]
        for j in range(1, min(M,i) + 1):
            s += q[j]*a[i-j]
        p[i] = s
    return p, q

#----------------------------------------------------------------------------#
#                                Polynomials                                 #
#----------------------------------------------------------------------------#

def polyval(coeffs, x, derivative=False):
    r"""
    Given coefficients `[c_n, \ldots, c_2, c_1, c_0]` and a number `x`,
    :func:`polyval` evaluates the polynomial

    .. math ::

        P(x) = c_n x^n + \ldots + c_2 x^2 + c_1 x + c_0.

    If *derivative=True* is set, :func:`polyval` simultaneously
    evaluates `P(x)` with the derivative, `P'(x)`, and returns the
    tuple `(P(x), P'(x))`.

        >>> from mpmath import *
        >>> polyval([3, 0, 2], 0.5)
        mpf('2.75')
        >>> polyval([3, 0, 2], 0.5, derivative=True)
        (mpf('2.75'), mpf('3.0'))

    The coefficients and the evaluation point may be any combination
    of real or complex numbers.
    """
    if not coeffs:
        return mpf(0)
    p = mpnumeric(coeffs[0])
    q = mpf(0)
    for c in coeffs[1:]:
        if derivative:
            q = p + x*q
        p = c + x*p
    if derivative:
        return p, q
    else:
        return p

def polyroots(coeffs, maxsteps=50, cleanup=True, extraprec=10, error=False):
    """
    Computes all roots (real or complex) of a given polynomial. The roots are
    returned as a sorted list, where real roots appear first followed by
    complex conjugate roots as adjacent elements. The polynomial should be
    given as a list of coefficients, in the format used by :func:`polyval`.
    The leading coefficient must be nonzero.

    With *error=True*, :func:`polyroots` returns a tuple *(roots, err)* where
    *err* is an estimate of the maximum error among the computed roots.

    **Examples**

    Finding the three real roots of `x^3 - x^2 - 14x + 24`::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> nprint(polyroots([1,-1,-14,24]), 4)
        [-4.0, 2.0, 3.0]

    Finding the two complex conjugate roots of `4x^2 + 3x + 2`, with an
    error estimate::

        >>> roots, err = polyroots([4,3,2], error=True)
        >>> for r in roots:
        ...     print r
        ...
        (-0.375 - 0.59947894041409j)
        (-0.375 + 0.59947894041409j)
        >>>
        >>> print err
        2.22044604925031e-16
        >>>
        >>> print polyval([4,3,2], roots[0])
        (2.22044604925031e-16 + 0.0j)
        >>> print polyval([4,3,2], roots[1])
        (2.22044604925031e-16 + 0.0j)

    The following example computes all the 5th roots of unity; that is,
    the roots of `x^5 - 1`::

        >>> mp.dps = 20
        >>> for r in polyroots([1, 0, 0, 0, 0, -1]):
        ...     print r
        ...
        1.0
        (-0.8090169943749474241 + 0.58778525229247312917j)
        (-0.8090169943749474241 - 0.58778525229247312917j)
        (0.3090169943749474241 + 0.95105651629515357212j)
        (0.3090169943749474241 - 0.95105651629515357212j)

    **Precision and conditioning**

    Provided there are no repeated roots, :func:`polyroots` can typically
    compute all roots of an arbitrary polynomial to high precision::

        >>> mp.dps = 60
        >>> for r in polyroots([1, 0, -10, 0, 1]):
        ...     print r
        ...
        -3.14626436994197234232913506571557044551247712918732870123249
        -0.317837245195782244725757617296174288373133378433432554879127
        0.317837245195782244725757617296174288373133378433432554879127
        3.14626436994197234232913506571557044551247712918732870123249
        >>>
        >>> print sqrt(3) + sqrt(2)
        3.14626436994197234232913506571557044551247712918732870123249
        >>> print sqrt(3) - sqrt(2)
        0.317837245195782244725757617296174288373133378433432554879127

    **Algorithm**

    :func:`polyroots` implements the Durand-Kerner method [1], which
    uses complex arithmetic to locate all roots simultaneously.
    The Durand-Kerner method can be viewed as approximately performing
    simultaneous Newton iteration for all the roots. In particular,
    the convergence to simple roots is quadratic, just like Newton's
    method.

    Although all roots are internally calculated using complex arithmetic,
    any root found to have an imaginary part smaller than the estimated
    numerical error is truncated to a real number. Real roots are placed
    first in the returned list, sorted by value. The remaining complex
    roots are sorted by real their parts so that conjugate roots end up
    next to each other.

    **References**

    1. http://en.wikipedia.org/wiki/Durand-Kerner_method

    """
    if len(coeffs) <= 1:
        if not coeffs or not coeffs[0]:
            raise ValueError("Input to polyroots must not be the zero polynomial")
        # Constant polynomial with no roots
        return []

    orig = mp.prec
    weps = +eps
    try:
        mp.prec += 10
        deg = len(coeffs) - 1
        # Must be monic
        lead = mpmathify(coeffs[0])
        if lead == 1:
            coeffs = map(mpmathify, coeffs)
        else:
            coeffs = [c/lead for c in coeffs]
        f = lambda x: polyval(coeffs, x)
        roots = [mpc((0.4+0.9j)**n) for n in xrange(deg)]
        err = [mpf(1) for n in xrange(deg)]
        # Durand-Kerner iteration until convergence
        for step in xrange(maxsteps):
            if max(err).ae(0):
                break
            for i in xrange(deg):
                if not err[i].ae(0):
                    p = roots[i]
                    x = f(p)
                    for j in range(deg):
                        if i != j:
                            try:
                                x /= (p-roots[j])
                            except ZeroDivisionError:
                                continue
                    roots[i] = p - x
                    err[i] = abs(x)
        # Remove small imaginary parts
        if cleanup:
            for i in xrange(deg):
                if abs(roots[i].imag) < weps:
                    roots[i] = roots[i].real
                elif abs(roots[i].real) < weps:
                    roots[i] = roots[i].imag * 1j
        roots.sort(key=lambda x: (abs(x.imag), x.real))
    finally:
        mp.prec = orig
    if error:
        err = max(err)
        err = max(err, ldexp(1, -orig+1))
        return [+r for r in roots], +err
    else:
        return [+r for r in roots]


#----------------------------------------------------------------------------#
#                                  ODE solvers                               #
#----------------------------------------------------------------------------#

def smul(a, x):
    """Multiplies the vector "x" by the scalar "a"."""
    R = []
    for i in range(len(x)):
        R.append(a*x[i])
    return R

def vadd(*args):
    """Adds vectors "x", "y", ... together."""
    assert len(args) >= 2
    n = len(args[0])
    rest = args[1:]
    for x in args:
        assert len(x) == n
    R = []
    for i in range(n):
        s = args[0][i]
        for x in rest:
            s += x[i]
        R.append(s)
    return R

def ODE_step_euler(x, y, h, derivs):
    """
    Advances the solution y(x) from x to x+h using the Euler method.

    derivs .... a python function f(x, (y1, y2, y3, ...)) returning
    a tuple (y1', y2', y3', ...) where y1' is the derivative of y1 at x.
    """
    X = derivs(y,x)
    return vadd(y, smul(h, X))

half = mpf(0.5)

def ODE_step_rk4(x, y, h, derivs):
    """
    Advances the solution y(x) from x to x+h using the 4th-order Runge-Kutta
    method.

    derivs .... a python function f(x, (y1, y2, y3, ...)) returning
    a tuple (y1', y2', y3', ...) where y1' is the derivative of y1 at x.
    """
    h2 = ldexp(h, -1)
    third = mpf(1)/3
    k1 = smul(h, derivs(y, x))
    k2 = smul(h, derivs(vadd(y, smul(half, k1)), x+h2))
    k3 = smul(h, derivs(vadd(y, smul(half, k2)), x+h2))
    k4 = smul(h, derivs(vadd(y, k3), x+h))
    v = []
    for i in range(len(y)):
        v.append(y[i] + third*(k2[i]+k3[i] + half*(k1[i]+k4[i])))
    return v

def odeint(derivs, x0, t_list, step=ODE_step_rk4):
    """
    Given the list t_list of values, returns the solution at these points.
    """
    x = x0
    result = [x]
    for i in range(len(t_list)-1):
        dt = t_list[i+1] - t_list[i]
        x = step(t_list[i], x, dt, derivs)
        result.append(x)
    return result

#----------------------------------------------------------------------------#
#                              Approximation methods                         #
#----------------------------------------------------------------------------#

# The Chebyshev approximation formula is given at:
# http://mathworld.wolfram.com/ChebyshevApproximationFormula.html

# The only major changes in the following code is that we return the
# expanded polynomial coefficients instead of Chebyshev coefficients,
# and that we automatically transform [a,b] -> [-1,1] and back
# for convenience.

# Coefficient in Chebyshev approximation
def chebcoeff(f,a,b,j,N):
    s = mpf(0)
    h = mpf(0.5)
    for k in range(1, N+1):
        t = cos(pi*(k-h)/N)
        s += f(t*(b-a)*h + (b+a)*h) * cos(pi*j*(k-h)/N)
    return 2*s/N

# Generate Chebyshev polynomials T_n(ax+b) in expanded form
def chebT(a=1, b=0):
    Tb = [1]
    yield Tb
    Ta = [b, a]
    while 1:
        yield Ta
        # Recurrence: T[n+1](ax+b) = 2*(ax+b)*T[n](ax+b) - T[n-1](ax+b)
        Tmp = [0] + [2*a*t for t in Ta]
        for i, c in enumerate(Ta): Tmp[i] += 2*b*c
        for i, c in enumerate(Tb): Tmp[i] -= c
        Ta, Tb = Tmp, Ta

def chebyfit(f, interval, N, error=False):
    """
    Computes a polynomial of degree N-1 that approximates the
    given function f on the interval [a, b]. With ``error=True``,
    :func:`chebyfit` also returns an accurate estimate of the
    maximum absolute error; that is, the maximum value of
    abs(f(x) - poly(x)) for x in [a, b].

    :func:`chebyfit` uses the Chebyshev approximation formula,
    which gives a nearly optimal solution: that is, the maximum
    error of the approximating polynomial is very close to
    the smallest possible for degree N.

    Chebyshev approximation is very useful if one needs repeated
    evaluation of an expensive function, such as function defined
    implicitly by an integral or a differential equation. (For
    example, it could be used to turn a slow mpmath function
    into a fast machine-precision version of the same.)

    **Examples**

    Here we use it to generate a low-degree approximation of
    f(x) = cos(x), valid on the interval [1, 2]::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> poly, err = chebyfit(cos, [1, 2], 5, error=True)
        >>> nprint(poly)
        [2.91682e-3, 0.146166, -0.732491, 0.174141, 0.949553]
        >>> nprint(err, 12)
        1.61351758081e-5

    The polynomial can be evaluated using ``polyval``::

        >>> nprint(polyval(poly, 1.6), 12)
        -0.0291858904138
        >>> nprint(cos(1.6), 12)
        -0.0291995223013

    Sampling the true error at 1000 points shows that the error
    estimate generated by ``chebyfit`` is remarkably good::

        >>> error = lambda x: abs(cos(x) - polyval(poly, x))
        >>> nprint(max([error(1+n/1000.) for n in range(1000)]), 12)
        1.61349954245e-5

    **Choice of degree**

    The degree N can be set arbitrarily high, to obtain an
    arbitrarily good approximation. As a rule of thumb, an
    N-term Chebyshev approximation is good to N/(b-a) decimal
    places (although this depends on how well-behaved f is).
    The cost grows accordingly: ``chebyfit`` evaluates the
    function (N^2)/2 times to compute the coefficients and an
    additional N times to estimate the error.

    **Possible issues**

    One should be careful to use a sufficiently high working
    precision both when calling ``chebyfit`` and when evaluating
    the resulting polynomial, as the polynomial is sometimes
    ill-conditioned. It is for example difficult to reach
    15-digit accuracy when evaluating the polynomial using
    machine precision floats, no matter the theoretical
    accuracy of the polynomial. (The option to return the
    coefficients in Chebyshev form should be made available
    in the future.)

    It is important to note the Chebyshev approximation works
    poorly if f is not smooth. A function containing singularities,
    rapid oscillation, etc can be approximated more effectively by
    multiplying it by a weight function that cancels out the
    nonsmooth features, or by dividing the interval into several
    segments.
    """
    a, b = AS_POINTS(interval)
    orig = mp.prec
    try:
        mp.prec = orig + int(N**0.5) + 20
        c = [chebcoeff(f,a,b,k,N) for k in range(N)]
        d = [mpf(0)] * N
        d[0] = -c[0]/2
        h = mpf(0.5)
        T = chebT(mpf(2)/(b-a), mpf(-1)*(b+a)/(b-a))
        for k in range(N):
            Tk = T.next()
            for i in range(len(Tk)):
                d[i] += c[k]*Tk[i]
        d = d[::-1]
        # Estimate maximum error
        err = mpf(0)
        for k in range(N):
            x = cos(pi*k/N) * (b-a)*h + (b+a)*h
            err = max(err, abs(f(x) - polyval(d, x)))
    finally:
        mp.prec = orig
        if error:
            return d, +err
        else:
            return d

def fourier(f, interval, N):
    """
    Computes the Fourier series of degree N of the given function
    on the interval [a, b]. More precisely, :func:`fourier` returns
    two lists (c, s) of coefficients (the cosine series and sine
    series, respectively), such that::

                   N
                  ___
                 \\
        f(x) ~=   )    c[k]*cos(n*m) + s[k]*sin(n*m)
                 /___
                 n = 0

    where m = 2*pi/(b-a).

    Note that many texts define the first coefficient as 2*c[0] instead
    of c[0]. The easiest way to evaluate the computed series correctly
    is to pass it to :func:`fourierval`.

    **Examples**

    The function f(x) = x has a simple Fourier series on the standard
    interval [-pi, pi]. The cosine coefficients are all zero (because
    the function has odd symmetry), and the sine coefficients are
    rational numbers::

        >>> from mpmath import *
        >>> mp.dps = 15
        >>> c, s = fourier(lambda x: x, [-pi, pi], 5)
        >>> nprint(c)
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        >>> nprint(s)
        [0.0, 2.0, -1.0, 0.666667, -0.5, 0.4]

    This computes a Fourier series of a nonsymmetric function on
    a nonstandard interval::

        >>> I = [-1, 1.5]
        >>> f = lambda x: x**2 - 4*x + 1
        >>> cs = fourier(f, I, 4)
        >>> nprint(cs[0])
        [0.583333, 1.12479, -1.27552, 0.904708, -0.441296]
        >>> nprint(cs[1])
        [0.0, -2.6255, 0.580905, 0.219974, -0.540057]

    It is instructive to plot a function along with its truncated
    Fourier series::

        >>> plot([f, lambda x: fourierval(cs, I, x)], I) #doctest: +SKIP

    Fourier series generally converge slowly (and may not converge
    pointwise). For example, if f(x) = cosh(x), a 10-term Fourier
    series gives an L^2 error corresponding to 2-digit accuracy::

        >>> I = [-1, 1]
        >>> cs = fourier(cosh, I, 9)
        >>> g = lambda x: (cosh(x) - fourierval(cs, I, x))**2
        >>> nprint(sqrt(quad(g, I)))
        4.67963e-3

    :func:`fourier` uses numerical quadrature. For nonsmooth functions,
    the accuracy (and speed) can be improved by including all singular
    points in the interval specification::

        >>> nprint(fourier(abs, [-1, 1], 0), 10)
        ([0.5000441648], [0.0])
        >>> nprint(fourier(abs, [-1, 0, 1], 0), 10)
        ([0.5], [0.0])

    """
    interval = AS_POINTS(interval)
    a = interval[0]
    b = interval[-1]
    L = b-a
    cos_series = []
    sin_series = []
    cutoff = eps*10
    for n in xrange(N+1):
        m = 2*n*pi/L
        an = 2*quadgl(lambda t: f(t)*cos(m*t), interval)/L
        bn = 2*quadgl(lambda t: f(t)*sin(m*t), interval)/L
        if n == 0:
            an /= 2
        if abs(an) < cutoff: an = mpf(0)
        if abs(bn) < cutoff: bn = mpf(0)
        cos_series.append(an)
        sin_series.append(bn)
    return cos_series, sin_series

def fourierval(series, interval, x):
    """
    Evaluates a Fourier series (in the format computed by
    by :func:`fourier` for the given interval) at the point x.

    The series should be a pair (c, s) where c is the
    cosine series and s is the sine series. The two lists
    need not have the same length.
    """
    cs, ss = series
    ab = AS_POINTS(interval)
    a = interval[0]
    b = interval[-1]
    m = 2*pi/(ab[-1]-ab[0])
    s = mpf(0)
    s += sum(cs[n]*cos(m*n*x) for n in xrange(len(cs)) if cs[n])
    s += sum(ss[n]*sin(m*n*x) for n in xrange(len(ss)) if ss[n])
    return s

if __name__ == '__main__':
    import doctest
    doctest.testmod()
