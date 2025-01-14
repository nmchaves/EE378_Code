import itertools
import numpy as np
import util
from portfolio import Portfolio
from olmar import OLMAR


class RMR(OLMAR):
    """"
    Robust Median Reversion Portfolio. Similar to OLMAR, except that it
    estimates the price relatives using the L1 median.

    Reference:
    Robust Median Reversion Strategy for On-Line Portfolio Selection
    by Huang et al:
    http://www.ijcai.org/Proceedings/13/Papers/296.pdf

    """
    def __init__(self, market_data, market_data_train=None, start=0, stop=None, window=20, eps=1.5, tau=0.001, max_iter=100,
                rebal_interval=1, window_range=range(5, 30, 3), eps_range=np.arange(1.1, 5.1, 0.2),
                 tune_interval=25, init_b=None, verbose=False, silent=False,
                 past_results_dir=None, new_results_dir=None, repeat_past=False):

        self.portfolio_type = 'RMR'

        if past_results_dir is not None:
            # Load in the previous results.
            # Set tau and past_dollars_history based on past tuning. Pass window,, eps, and init_b to superclass
            # where they'll be used for initialization.
            hyperparams_dict = util.load_hyperparams(past_results_dir, ['Tau'])
            tau = hyperparams_dict['Tau']

        self.tau = tau  # tolerance level
        self.max_iter = max_iter

        super(RMR, self).__init__(market_data=market_data, market_data_train=market_data_train, start=start, stop=stop, window=window, eps=eps,
                                  rebal_interval=rebal_interval, window_range=window_range, eps_range=eps_range,
                                  tune_interval=tune_interval, init_b=init_b, verbose=verbose, silent=silent,
                                  past_results_dir=past_results_dir, new_results_dir=new_results_dir, repeat_past=repeat_past)

    def predict_price_relatives(self, day):
        """
        This function predicts the price relative vector at the end of |day| based on the L1 median
        in the window |day|-w to |day|-1:


        :param day: The day to predict the closing price relatives for.
        (This plays the role of t+1 in the above equation.)
        :return: The predicted price relatives vector.
        """

        window, window_cl, today_op = self.get_window_prices(day, self.window)
        avail_today = util.get_avail_stocks(today_op)
        num_avail = sum(avail_today)
        today_op = np.reshape(today_op, newshape=(1, self.num_stocks))
        window_prices = np.append(window_cl, today_op, axis=0)

        avail_full_window = np.ones(self.num_stocks)
        for i in range(self.num_stocks):
            cur_window = window_prices[:, i]  # Recent prices for stock i
            if np.isnan(cur_window).any():
                avail_full_window[i] = 0  # Stock is not available for at least 1 day in the window
        num_avail_full_window = int(sum(avail_full_window))

        window_pr_avail_full_window = np.zeros(shape=(window+1, num_avail_full_window))
        window_pr_avail_today = np.zeros(shape=(window+1, num_avail))
        op_avail_today = np.zeros(shape=(1, num_avail))
        col_today = 0
        col_full = 0
        for i, is_avail in enumerate(avail_today):
            if is_avail:
                cur_window = window_prices[:, i]  # Note: Some elements here may be nan
                window_pr_avail_today[:, col_today] = cur_window
                op_avail_today[0, col_today] = today_op[0, i]
                col_today += 1

                if avail_full_window[i]:
                    window_pr_avail_full_window[:, col_full] = cur_window
                    col_full += 1

        # Get median of each stock in the window (avoid nans)
        mu = np.zeros(sum(avail_today))
        mu_avail_full_window = np.zeros(int(sum(avail_full_window)))
        j = 0
        for i, _ in enumerate(mu):
            # Get window of prices for the current stock (only include non-nan prices)
            cur_window = window_pr_avail_today[:, i]
            cur_window = cur_window[np.isfinite(cur_window)]
            mu[i] = np.median(cur_window)
            if np.isnan(mu[i]):
                print 'median is nan!'

            if avail_full_window[i]:
                mu_avail_full_window[j] = mu[i]
                j += 1

        for i in range(1, self.max_iter):
            prev_mu = mu_avail_full_window
            mu_avail_full_window = self.T_func(mu_avail_full_window, window_pr_avail_full_window)
            L1_dist = np.linalg.norm((prev_mu-mu_avail_full_window), ord=1)
            thresh = self.tau * np.linalg.norm(mu_avail_full_window, ord=1)

            if L1_dist <= thresh:
                break

        mu_final = np.zeros(sum(avail_today))
        j = 0
        for i, med_avail_today in enumerate(mu):
            if avail_full_window[i]:
                # Use the T function's price
                mu_final[i] = mu_avail_full_window[j]
                j += 1
            else:
                # Just use the median of available prices
                mu_final[i] = med_avail_today

        # Use mu as the predicted raw closing prices.
        price_rel_avail = util.silent_divide(mu_final, op_avail_today)
        price_rel = np.zeros(shape=(1, self.num_stocks))
        col = 0
        for i, is_avail in enumerate(avail_today):
            if is_avail:
                price_rel[0, i] = price_rel_avail[:, col]
                col += 1
        return price_rel[0]

    def T_func(self, mu, window_cl):
        """
        The function described in Proposition 1 of Huang et al for updating mu.

        Note: Here, I assume eta (as described in Huang et al) to be 0, because it's
        extremely unlikely that the price vector will never remain constant over the whole window.

        The smallest window that would ever be used would be on the 2nd day of trading, when the window_cl
        vector would consist of the previous day's closing prices and the current day's opening prices.
        Even in this scenario, the likelihood that both price vectors will be the same is vanishing.
        """

        # Compute R tilde
        s1 = 0
        s2 = 0
        R_tilde = 0
        for cl in window_cl:
            diff = cl - mu
            if np.any(diff):
                # Check that diff is nonzero, because we need to divide by it
                dist = np.linalg.norm((cl-mu), ord=2)
                s1 += 1.0 / dist
                s2 += np.nan_to_num(np.true_divide(cl, dist))
                R_tilde += diff * 1.0 / dist

        T_tilde = s2 * 1.0 / s1
        return T_tilde

    def tune_hyperparams(self, cur_day):
        # Create new instances of this portfolio with various hyperparameter settings
        # to find the best constant hyperparameters in hindsight

        tune_duration = 10  # Tune over the last 2 weeks
        if cur_day > tune_duration:
            start_day = cur_day - tune_duration
        else:
            # Not worth tuning yet
            return

        hyperparam_space = [self.window_range, self.eps_range]
        hyp_combos = list(itertools.product(*hyperparam_space))

        init_b = self.b_history[:,cur_day-tune_duration]   # Allocation used at beginning of tuning period

        # Compute sharpe ratios for each setting of hyperparams
        sharpe_ratios = []
        for (win, eps) in hyp_combos:
            cur_portfolio = RMR(market_data=self.data, start=start_day, stop=cur_day,
                                  init_b=init_b, window=win, eps=eps, tune_interval=None, verbose=False, silent=True)
            cur_portfolio.run(start_day, cur_day)
            cur_dollars_history = cur_portfolio.get_dollars_history()
            sharpe_ratios.append(util.empirical_sharpe_ratio(cur_dollars_history))

        best_window, best_eps = hyp_combos[sharpe_ratios.index(max(sharpe_ratios))]
        self.window = best_window
        self.eps = best_eps
        return

    def print_results(self):
        if self.verbose:
            print 30 * '-'
            print 'Performance for RMR:'
            print 30 * '-'
        Portfolio.print_results(self)

    def save_results(self):
        print 'saving RMR'
        save_dir = self.new_results_dir

        # Dollars History File
        util.save_dollars_history(save_dir=save_dir, dollars=self.dollars_op_history, portfolio_type='RMR')

        # Portfolio Allocation History File
        util.save_b_history(save_dir=save_dir, b_history=self.b_history, portfolio_type='RMR')

        # Hyperparameters File
        util.save_hyperparams(save_dir=save_dir, hyperparams_dict=self.get_hyperparams_dict(), portfolio_type='RMR')

    def get_hyperparams_dict(self):
        hyperparams = {
            'Window': str(self.window),
            'Epsilon': str(self.eps),
            'Tau': str(self.tau)
        }
        return hyperparams

    def load_previous_hyperparams(self, past_results_dir):
        hyperparams_dict = util.load_hyperparams(past_results_dir=past_results_dir)

        if 'Tau' in hyperparams_dict:
            tau = hyperparams_dict['Tau']
        else:
            raise Exception('Tau parameter not saved in results file in ' + past_results_dir)
        return tau




