"""
    Utilities file
"""
import numpy as np
from scipy import io
from math import sqrt, isnan
import market_data
from constants import cost_per_dollar


def load_matlab_sp500_data(file_path, start=0):
    """
    Get raw stock market data from Matlab file in |file_path|.
    Converts all nan values to 0.

    :param file_path: Path to the data file (must be a .mat file)
    :return: MarketData object containing stock market data.
    """
    mat = io.loadmat(file_path)
    train_vol = np.array(mat['test_vol'])[start:, :]  # Volume for each stocks on each day
    train_op = np.array(mat['test_op'])[start:, :]
    train_lo = np.array(mat['test_lo'])[start:, :]
    train_hi = np.array(mat['test_hi'])[start:, :]
    train_cl = np.array(mat['test_cl'])[start:, :]

    train_stocks = [name[0] for name in np.array(mat['test_stocks'])[0]]  # Ticker names for all 497 stocks
    return market_data.MarketData(train_vol, train_op, train_lo, train_hi, train_cl, train_stocks)


def get_price_relatives(raw_prices):
    """
    Converts raw stock market prices to relative price changes.
    Sets the day 1 price relatives to be 0 by default. # TODO: change this when working with test set!!

    :param raw_prices: (NUM_DAYS x NUM_STOCKS) Array of raw stock market prices
    :return: Array of relative price changes
    """
    price_relatives = np.zeros(raw_prices.shape)
    prev_row = raw_prices[0]
    for (i, row) in enumerate(raw_prices[1:]):
        for (j, price) in enumerate(row):
            prev_price = prev_row[j]
            if price != 0 and prev_price != 0:
                price_relatives[i+1, j] = 1.0 * price / prev_price
        prev_row = row
    return price_relatives


def get_standardized_prices(raw_prices):
    n_stocks = raw_prices.shape[1]
    n_days = raw_prices.shape[0]
    prices_scaled = np.zeros(raw_prices.shape)

    for col in range(n_stocks):
        cur_raw = np.nan_to_num(raw_prices[:, col])
        cur_std = np.std(cur_raw)
        if cur_std != 0:
            cur_scaled = (1.0 / np.std(cur_raw)) * (cur_raw - np.mean(cur_raw))
        else:
            cur_scaled = np.zeros(n_days)
        prices_scaled[:, col] = cur_scaled

    return prices_scaled


def get_avail_stocks(op_prices):
    """
    Based on the opening prices for a given day, get the set of stocks that one can
    actually purchase today (not all stocks are on the market at all times)

    :param op_prices: The list of opening prices
    :return: Binary array of available stocks (1 means available, 0 means unavailable
    """
    avail_stocks = [0] * len(op_prices)
    for i, price in enumerate(op_prices):
        # If price is a valid number > 0, then we can purchase the
        # stock at the end of the day
        if (not isnan(price)) and price > 0:
            avail_stocks[i] = 1
    return avail_stocks


def get_uniform_allocation(num_stocks, op_prices):
    b = np.zeros(num_stocks)
    available_stocks = get_avail_stocks(op_prices)
    num_stocks_avail = np.count_nonzero(available_stocks)
    frac = 1.0 / num_stocks_avail  # fractional allocation per stock

    for (i, is_avail) in enumerate(available_stocks):
        if is_avail:
            b[i] = frac
    return b


def dollars_in_stocks(shares_holding, share_prices):
    # Set any nan values in share_prices to 0
    share_prices = np.nan_to_num(share_prices)

    # Return total amount of money held in stocks
    return np.dot(shares_holding, share_prices)


def get_float_array_from_file(path):
    """
    This function takes a path to a file containing a tab-delimited
    text file and converts that file into an array.

    :param path: Path to the file
    :return: The array
    """
    f = open(path)
    for line in f:
        return map(float, line.split('\t'))
        break


def empirical_sharpe_ratio(dollars):
    """
    Compute the empirical Sharpe Ratio:
        x_bar = (final_dollars - init_dollars) / num_days
        var = sqrt( (1/num_days) * (sum(x_i-mean(x_bar)))^2 )
        Sharpe ratio = mean(x) * sqrt(num_days) / var

    :param dollars: # of dollars held at the end of each day over time.
    :return: Sharpe ratio
    """

    return_seq = np.log(dollars[1:] / dollars[:-1])
    sharpe = np.sqrt(252) * np.mean(return_seq) / np.std(return_seq)
    return sharpe

    """
    num_days = len(dollars)
    x = [dollars[i] - dollars[i-1] for i in range(1, num_days)]
    x_bar = np.mean(x)
    std_dev = np.std(x)
    return (1.0 * x_bar / std_dev) * sqrt(252)  # 252 is approximate # of trading days in 1 year
    """


def predict_prices(cur_day, market_data):
    """
        Predict closing prices at the end of |cur_day|
    """
    # TODO: use autoregressive or some other ML approach to estimate price relatives at the end of the day
    #est_prs = []  # estimated price relatives
    # Simplest baseline: Assume prices remain the same as open
    est_prs = np.nan_to_num(market_data.get_op(relative=True)[cur_day, :])
    return est_prs


def get_dollars_ipy(op, cl, value_op, portfolio, prev_dollars):
        """
        Calculate a portfolio's wealth for the end of |cur_day| after buying/selling stocks
        at their closing prices.
        Uses code from course staff.
        """
        isActive = np.isfinite(op)

        """
        # The value of our portfolio at the end of Day t before paying transaction costs
        cl = test_cl[t,:]
        value_vec = value_op_seq[t] * portfolio_seq[:,t]
        growth = cl[isActive] / last_close_price[isActive]-1
        growth[np.isnan(growth)] = 0
        revenue_vec = value_vec[isActive] * growth
        value_vec[isActive] = value_vec[isActive] + revenue_vec
        value_cl_seq[t] = value_op_seq[t] + np.sum(revenue_vec)
        """


def get_dollars_old(cur_day, prev_dollars, prev_b, cur_b, cpr):
        """
        Calculate a portfolio's wealth for the end of |cur_day| after buying/selling stocks
        at their closing prices.

        :param cur_day: Current day (0-based s.t. cur_day=0 corresponds to the 1st day)
        :param prev_dollars: # of dollars held in stocks after making trades at end of previous day
        :param prev_b: Allocation at the end of |cur_day|-1.
        :param cur_b: Allocation at the end of |cur_day|.
        :param cpr: Closing price relatives for the end of |cur_day|.
        :return: The new # of dollars held
        """
        #  0.91070146333713753
        # TODO: check this. This updates the money held before trading (this accounts for shorting)
        dollars_before_trading = 0
        for (pb_i, cpr_i) in zip(prev_b, cpr):
            if pb_i > 0:
                dollars_before_trading += pb_i * cpr_i
            elif pb_i < 0:
                # This stock is being shorted. We made money if the price decreased
                dollars_before_trading += abs(pb_i) * 1.0 / cpr_i
        dollars_before_trading *= prev_dollars

        #dollars_before_trading = prev_dollars * np.dot(prev_b, cpr)
        if dollars_before_trading <= 0:
            print 'The portfolio ran out of money on day ', str(cur_day), '!'
            exit(0)

        L1_dist = np.linalg.norm((prev_b - cur_b), ord=1)  # L1 distance between new and old allocations
        dollars_trading = dollars_before_trading * L1_dist  # # of dollars that need to be traded to...
        # ...reallocate (this already includes costs of both buying and selling!)
        new_dollars = dollars_before_trading - dollars_trading * cost_per_dollar

        if new_dollars <= 0:
            print 'The portfolio ran out of money on day ', str(cur_day), '!'
            exit(0)
        else:
            return new_dollars


def k_nearest_neighbors(stock, market_matrix, k, market_norms, distance_fn = None):
    '''
    Given a market window (stocks x prices), select the k stocks that are
    "closest" to the given stock with respect to some metric distance_fn,
    or L2 distance if no function is specified.

    :param stock:           vector of stock data
    :param market_matrix:   matrix of all stock data for a particular market window
                            (must be same size as stock vector)
    :param k:               number of neighbors to compute
    :param distance_fn:     function handle of custom distance measurement fn
    '''

    assert stock.shape[0] == market_matrix.shape[1], "Your stock vector should be the same length as your market matrix."
    m,n = market_matrix.shape

    distance = np.zeros(m)
    if distance_fn:
        for index in range(m):
            distance[index] = distance_fn(stock, market_matrix[index,:])
    else:
        stock_norm = np.dot(stock, np.transpose(stock))
        distance = stock_norm - 2 * np.dot(market_matrix,stock) + market_norms

    # Sort in ascending order and get indices of k smallest distances
    sorted_indices = np.argsort(distance)
    return sorted_indices[:k]


def get_available_inds(avail_stocks):
    '''
    Calculate the indices of the day's available stocks from a boolean np array
    specifying which stocks are valid
    '''
    num_total_stocks = len(avail_stocks)
    return np.asarray([i for i in range(num_total_stocks) if avail_stocks[i] > 0])


def save_results(output_fname, dollars):
    print 'Saving dollar value to file: ', output_fname
    output_file = open(output_fname, 'w')
    output_file.write('Empricial Sharpe Ratio: ' + str(empirical_sharpe_ratio(dollars)) + '\n')
    output_file.write('\t'.join(map(str, dollars)) + '\n')
    output_file.close()


def silent_divide(a,b):
    """
    Element-wise division of the array a by the array b. This function converts nan to 0 and inf to a large #
    using np.nan_to_num.

    The function also silences the runtime warning "invalid value encountered in true_divide", b/c we handle
    these values using np.nan_to_num.
    """
    with np.errstate(invalid='ignore'):
        return np.nan_to_num(np.true_divide(a, b))


def rebalance(value_vec, value_realizable, portfolio_dst):
    """
    (Referenced from the course staff)

    % This function simulates the process of rebalancing. The key difficulty
    % here is to compute the transaction cost, i.e., to solve the equation
    %
    % sum( cost_rate * abs( portfolio_dst .* (value_realizable - C) -
    % value_vec) ) = C
    %
    % where C is the total transcation cost. We use the Banach contraction
    % theorem to solve this equation, with convergence rate cost_rate^t for
    % t-th iteration.

    % Input:
    %%% value_vec: current values of each active stock
    %%% value_realizable: total cash realizable value
    %%% portfolio_dst: the desired portfolio after rebalancing
    %%% cost_rate: ratio of transactions cost (0.0005 in our case)

    % Output:
    %%% new_value_vec: the value vector after rebalancing
    %%% trans_cost: the total transaction cost"""

    iter_num = 7
    trans_cost = 0
    for iter in range(iter_num):
        trans_cost = np.sum(cost_per_dollar * np.abs(portfolio_dst * \
                                               (value_realizable-trans_cost)-value_vec))

    new_value_vec = portfolio_dst * (value_realizable - trans_cost)
    return new_value_vec, trans_cost


def save_dollars_history(save_dir, dollars, portfolio_type):
    dollars_hist_file = save_dir + 'dollars_history.txt'
    header = 'Dollars held by ' + portfolio_type + ' portfolio at market open on each day of training set.'
    np.savetxt(dollars_hist_file, dollars, delimiter='\t', header=header)
    return


def save_b_history(save_dir, b_history, portfolio_type):
    b_hist_file = save_dir + 'b_history.txt'
    header = portfolio_type + ' portfolio allocation on each day of training set.'
    np.savetxt(b_hist_file, b_history, delimiter='\t', header=header)
    return


def save_hyperparams(save_dir, hyperparams_dict, portfolio_type):

    final_hyp_file = save_dir + 'hyperparams.txt'
    out_file = open(final_hyp_file, 'w')
    header = '# ' + portfolio_type + ' hyperparameters selected by online tuning on each day of the training set.\n'
    col_titles = '# Param\tFinal_Value\n'
    out_file.write(header + col_titles)

    for key, val in hyperparams_dict.iteritems():
        out_file.write(key + '\t' + val + '\n')
    out_file.close()


def load_hyperparams(past_results_dir, params):
    """

    :param past_results_dir: Path to directory containing stored hyperparams.
    :param params: List of string of hyperparameter names
    :return: Dictionary mapping hyperparm strings to their values.
    """

    hyperparams_dict = {}
    hyp_file = open(past_results_dir + 'hyperparams.txt')
    for line in hyp_file:
        if line[0] != '#':
            vals = line.rstrip().split('\t')
            param = vals[0]
            if param in params:
                val = float(vals[1])
                hyperparams_dict[param] = val
    return hyperparams_dict

