import numpy as np
from selection.tests.instance import gaussian_instance
from selection.bayesian.initial_soln import selection
from selection.bayesian.sel_probability import selection_probability
from selection.bayesian.non_scaled_sel_probability import no_scale_selection_probability
from selection.bayesian.sel_probability2 import cube_subproblem, cube_gradient, cube_barrier, selection_probability_objective
from selection.bayesian.dual_optimization import dual_selection_probability
from selection.randomized.api import randomization
from matplotlib import pyplot as plt

#fixing n, p, true sparsity and signal strength
n = 20
p = 3
s = 1
snr = 5

#sampling the Gaussian instance
X_1, y, true_beta, nonzero, noise_variance = gaussian_instance(n=n, p=p, s=s, sigma=1, rho=0, snr=snr)
random_Z = np.random.standard_normal(p)
#getting randomized Lasso solution
sel = selection(X_1,y, random_Z)

#proceed only if selection is non-empty
if sel is not None:
    lam, epsilon, active, betaE, cube, initial_soln = sel
    print epsilon, lam, betaE
    noise_variance = 1
    nactive=betaE.shape[0]
    active_signs = np.sign(betaE)
    tau=1
    X_perm=np.zeros((n,p))
    X_perm[:,:nactive]=X_1[:,active]
    X_perm[:,nactive:]=X_1[:,~active]
    V=-X_perm
    X_active=X_perm[:,:nactive]
    X_nactive=X_perm[:,nactive:]
    B_sel=np.zeros((p,p))
    B_sel[:,:nactive]=np.dot(X_perm.T,X_perm[:,:nactive])
    B_sel[:nactive, :nactive]+= epsilon*np.identity(nactive)
    B_sel[nactive:, nactive:]=lam*np.identity((p-nactive))
    gamma_sel=np.zeros(p)
    gamma_sel[:nactive]=lam*np.sign(betaE)

    #box_initial = np.random.uniform(-1, 1,(p-nactive))
    #box_grad = np.true_divide(1,1-box_initial)-np.true_divide(1,1+box_initial)
    #coef_grad = -np.true_divide(1,betaE)+np.true_divide(1,1+betaE)
    #grad_barrier = np.append(coef_grad,box_grad)
    #dual_initial = np.dot(np.linalg.inv(B_sel.T),grad_barrier)
    feasible = np.append(-np.fabs(np.random.standard_normal(nactive)),np.random.uniform(-1, 1,(p-nactive)))
    dual_initial = np.dot(np.linalg.inv(B_sel.T),feasible)
    #print nactive, dual_initial

    parameter = np.ones(nactive)
    mean = X_1[:, active].dot(parameter)


    def test_selection_probability_gaussian():

        lagrange = lam * np.ones(p)

        sel_prob = selection_probability_objective(X_1,
                                                  np.fabs(betaE),
                                                  active,
                                                  active_signs,
                                                  lagrange,
                                                   mean,
                                                   noise_variance, randomization.isotropic_gaussian((p,), 1.),epsilon)
        return -sel_prob.minimize()[1],sel_prob.minimize()[0]


    def test_my_funct():

        sel = selection_probability(V, B_sel, gamma_sel, noise_variance, tau, lam, y, betaE, cube)

        return sel.optimization(parameter)[0]-np.true_divide(np.dot(
            mean.T,mean),2*noise_variance)-np.true_divide(np.dot(gamma_sel[:nactive].T,gamma_sel[:nactive]),2*(tau**2)),\
               sel.optimization(parameter)[1]

    def test_dual():

        lagrange = lam * np.ones(p)

        sel_dual = dual_selection_probability(X_1,
                                              dual_initial,
                                              active,
                                              active_signs,
                                              lagrange,
                                              mean,
                                              noise_variance,
                                              randomization.isotropic_gaussian((p,), 1.),
                                              epsilon)

        return sel_dual.minimize()[1]-np.true_divide(np.dot(mean.T,mean),2*noise_variance), sel_dual.minimize()[0]


    #print test_dual()

    #print test_selection_probability_gaussian(), test_my_funct()

    def test_one_sparse():
        if nactive==1:
            snr_seq = np.linspace(-10, 10, num=100)
            num = snr_seq.shape[0]
            #sel_non_scaled_seq = []
            sel_scaled_seq = []
            sel_grad_descent = []
            lagrange = lam * np.ones(p)
            for i in range(snr_seq.shape[0]):
                parameter = snr_seq[i]
                print "parameter value", parameter
                mean = X_1[:, active].dot(parameter)
                sel_non_scaled = no_scale_selection_probability(V, B_sel, gamma_sel, noise_variance, tau, lam, y, betaE, cube)
                sel_scaled= selection_probability(V, B_sel, gamma_sel, noise_variance, tau, lam, y, betaE, cube)

                sel_prob_grad_descent = selection_probability_objective(X_1, np.fabs(betaE), active, active_signs,
                                                                        lagrange, mean,
                                                                        noise_variance,
                                                                        randomization.isotropic_gaussian((p,), 1.),
                                                                        epsilon)

                #sel_non_scaled_val = sel_non_scaled.optimization(parameter * np.ones(nactive))[0] - np.true_divide(
                #    np.dot(mean.T, mean), 2 * noise_variance) - np.true_divide(
                #    np.dot(gamma_sel[:nactive].T, gamma_sel[:nactive]),2 * (tau ** 2))

                sel_scaled_prob = sel_scaled.optimization(parameter*np.ones(nactive),method="softmax_barrier")
                sel_scaled_prob_min = sel_scaled_prob[0]\
                                 -np.true_divide(np.dot(mean.T,mean),2*noise_variance)\
                                 -np.true_divide(np.dot(gamma_sel[:nactive].T,gamma_sel[:nactive]),2*(tau**2))
                                      #sel_scaled_prob[1]

                print "log selection probability", sel_scaled_prob_min, -sel_prob_grad_descent.minimize()[1]

                #sel_non_scaled_seq.append(sel_non_scaled_val)
                sel_scaled_seq.append(sel_scaled_prob_min)
                sel_grad_descent.append(-sel_prob_grad_descent.minimize()[1])

            #sel_non_scaled_seq = np.reshape(sel_non_scaled_seq, num)
            #sel_scaled_seq = np.reshape(sel_scaled_seq, num)
            #print np.shape(sel_non_scaled_seq), np.shape(sel_scaled_seq), np.shape(sel_grad_descent)

            #plt.clf()
            #plt.title("sel_prob")
            #plt.plot(snr_seq, sel_non_scaled_seq, color="b")
            #plt.plot(snr_seq, sel_scaled_seq, color="r")
            #plt.plot(snr_seq, sel_grad_descent, color="m")
            #plt.savefig('my_sel_prob.png')
            #plt.close()

    test_one_sparse()

    def test_sel_probs_scalings():
        parameter = np.fabs(np.random.standard_normal(nactive))
        lagrange = lam * np.ones(p)
        mean = X_1[:, active].dot(parameter)
        sel_non_scaled = no_scale_selection_probability(V, B_sel, gamma_sel, noise_variance, tau, lam, y, betaE, cube)
        sel_scaled = selection_probability(V, B_sel, gamma_sel, noise_variance, tau, lam, y, betaE, cube)
        sel_prob_grad_descent = selection_probability_objective(X_1, np.fabs(betaE), active, active_signs,
                                                                lagrange, mean,
                                                                noise_variance,
                                                                randomization.isotropic_gaussian((p,), 1.),
                                                                epsilon)
        sel_non_scaled_val = sel_non_scaled.optimization(parameter * np.ones(nactive))[0] - np.true_divide(
                    np.dot(mean.T, mean), 2 * noise_variance) - np.true_divide(
                    np.dot(gamma_sel[:nactive].T, gamma_sel[:nactive]),2 * (tau ** 2))

        sel_scaled_val = sel_scaled.optimization(parameter * np.ones(nactive))[0] - np.true_divide(np.dot(
            mean.T, mean), 2 * noise_variance) - np.true_divide(np.dot(gamma_sel[:nactive].T, gamma_sel[:nactive]),
                                                                2 * (tau ** 2))

        print "log selection probability", sel_non_scaled_val, sel_scaled_val, -sel_prob_grad_descent.minimize()[1]


    #test_sel_probs_scalings()

    def test_sel_barrier_method():
        parameter = np.random.standard_normal(nactive)
        mean = X_1[:, active].dot(parameter)
        sel = selection_probability(V, B_sel, gamma_sel, noise_variance, tau, lam, y, betaE, cube)
        sel_val_log = sel.optimization(parameter * np.ones(nactive),method="log_barrier")[0] - np.true_divide(np.dot(
            mean.T, mean), 2 * noise_variance) - np.true_divide(np.dot(gamma_sel[:nactive].T, gamma_sel[:nactive]),
                                                                2 * (tau ** 2))
        sel_val_softmax = sel.optimization(parameter * np.ones(nactive),method="softmax_barrier")[0] - np.true_divide(np.dot(
            mean.T, mean), 2 * noise_variance) - np.true_divide(np.dot(gamma_sel[:nactive].T, gamma_sel[:nactive]),
                                                                2 * (tau ** 2))

        print "log selection probability", sel_val_log, sel_val_softmax


    #test_sel_barrier_method()

    def test_different_barriers():
        if nactive==1:
            snr_seq = np.linspace(0, 10, num=10)
            for i in range(snr_seq.shape[0]):
                parameter = snr_seq[i]
                mean = X_1[:, active].dot(parameter)
                print "parameter value", parameter
                sel = selection_probability(V, B_sel, gamma_sel, noise_variance, tau, lam, y, betaE, cube)
                sel_log_val = sel.optimization(parameter*np.ones(nactive),method="log_barrier")[0]-\
                              np.true_divide(np.dot(mean.T,mean),2*noise_variance)\
                              -np.true_divide(np.dot(gamma_sel[:nactive].T,gamma_sel[:nactive]),2*(tau**2))
                sel_softmax_val = sel.optimization(parameter*np.ones(nactive),method="softmax_barrier")[0]\
                                  -np.true_divide(np.dot(mean.T,mean),2*noise_variance)\
                                  -np.true_divide(np.dot(gamma_sel[:nactive].T,gamma_sel[:nactive]),2*(tau**2))
                print "log selection probability", sel_log_val, sel_softmax_val


    #test_different_barriers()


















