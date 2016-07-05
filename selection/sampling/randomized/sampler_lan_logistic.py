from copy import copy

import numpy as np
import regreg.api as rr

# I needed sampler_new since projected Langevin for step_simplex needed hessian and that was not available in penalty class
# this one has everything the same as sampler just has self.hesssian as well

class selective_sampler(object):

    def __init__(self, loss,
                 linear_randomization,  #set in e.g. tests/test_logistic.py, the model selection done based on this randomization
                 quadratic_coef,  # \epsilon in \frac{\epsilon}{2}\|\beta\|_2^2 term in the objective we are minimizing
                 randomization,
                 penalty,
                 solve_args={'tol':1.e-10, 'min_its':100, 'max_its':500}):

        (self.loss,
         self.linear_randomization,
         self.randomization,
         self.quadratic_coef) = (loss,
                                 linear_randomization,
                                 randomization,
                                 quadratic_coef)
        # initialize optimization problem

        self.penalty = penalty
        self.problem = rr.simple_problem(loss, penalty)

        random_term = rr.identity_quadratic(
                                quadratic_coef, 0,
                                self.linear_randomization, 0)

        self.initial_soln = self.problem.solve(random_term,    # model selection, initial solution set here
                                               **solve_args)
        self.initial_grad = self.loss.smooth_objective(self.initial_soln,
                                                       mode='grad')

        #self.hessian = self.loss.hessian() ## ADDED since needed for projected Langevin used in step_simplex in penalty class
        self.opt_vars = self.penalty.setup_sampling( \
            self.initial_grad,
            #self.hessian,  ## ADDED
            self.initial_soln,
            self.linear_randomization,
            self.quadratic_coef)

    def setup_sampling(self, data, loss_args={}):

        self.loss.setup_sampling(data, **loss_args)
        self.cur_grad = self.loss.smooth_objective(self.initial_soln, 'grad')
        #self.hessian = self.loss.hessian() # added since needed for projected Langevin in step_simplex

        self.penalty.setup_sampling(self.initial_grad,
                                    #self.hessian,
                                    self.initial_soln,
                                    self.linear_randomization,
                                    self.quadratic_coef)

        self.state = [self.loss.data.copy(), self.opt_vars]

    def logpdf(self, state):
        """
        Log density of the randomization density, i.e. computes log of
            g(-\grad l(\beta) - \epsilon\beta - \grad P(\beta)), P - penalty, e.g. \lambda\|\beta\|_1 for the lasso
            plus log of jacobian.
            Recall the objective: min l(\beta)+P(\beta)+\frac{\epsilon}{2}\|\beta\|_2^2+w^T\beta, implies
            -w = \epsilon\beta+\grad P(\beta)+\grad l(\beta)
        """

        data, opt_vars = state   # opt_vars=(simplex, cube) in penalty class (e.g. norms\lasso.py)
        # the following is an important step that makes param as (signs*simplex, 0), subgrad = (signs, cube),
        # opt_vec = \epsilon\beta+subgrad (subgrad = \grad P(\beta), gradient of the penalty)
        # opt_vec becomes quadratic_coef*params+subgrad in penalty class
        param, subgrad, opt_vec = self.penalty.form_optimization_vector(opt_vars)
        gradient = self.loss.gradient(data, param)
        hessian =  self.loss.hessian
        log_jacobian = self.penalty.log_jacobian(hessian)
        val = - gradient - opt_vec

        return self.randomization.logpdf(val).sum() + log_jacobian   # sum since we assume randomization is iid


class selective_sampler_MH_lan_logistic(selective_sampler):

    def sampling(self,
                 ndraw=7000,
                 burnin=3000):
        """
        This function provides samples (data, \beta, subgrad) from
        normal_distribution(data)*g(gradient+epsilon*\beta+\epsilon(\beta 0))*jacobian,
        where gradient = \grad l(\beta) is a function of data and parameter \beta.
        """

        samples = []

        for i in range(ndraw + burnin):
            sample = self.next()
            if (i >= burnin): #and (i % 3==0):
                samples.append(copy(sample))
        return samples

    def __iter__(self):
        return self

    def next(self):
        """
        Gibbs sampler:
        calls one-step MH for the data vector (step_data in loss class), then one-step MH for simplex and moves cube vector
        (the last two done under step_variables in the penalty class)
        """

        # updates data according to MH step (might not actually move depending whether accepts or rejects)
        # step_data written in losses/base.py

        data, opt_vars = self.state
        param, subgrad, opt_vec = self.penalty.form_optimization_vector(opt_vars)
        gradient = self.loss.gradient(data, param)
        #val = - gradient - opt_vec
        hessian = self.loss.hessian

        #XTXE = self.loss._XTXE
        SigmaTinv = self.loss._inv_cov_beta_bar
        P = self.loss.P
        R = self.loss.R
        #self.state[0] = self.loss.step_data(self.state, self.logpdf)  # self.state[0] is the data vector

        # update the gradient
        #param = self.penalty.form_parameters(self.state[1]) # (beta_E, 0)
        #self.cur_grad = self.loss.gradient(self.state[0], param) # gradient is \grad l(\beta), a function of
                    # data vector (self.state[0]) and beta (param)

        # step_variables calls step_simplex and step_cube in e.g. norms/lasso.py
        # step_simplex moves according to MH step and step_cube draws an immediate sample since its density conditional on
        # everything else has explicit form (more in penalty class)
        data, opt_vars = self.penalty.step_variables(self.state, self.randomization, self.logpdf, gradient, hessian, SigmaTinv, P,R)
        #betaE, subgrad = opt_vars

        # update the optimization variables.
        self.state[0] = data
        self.state[1] = opt_vars

        return self.state
