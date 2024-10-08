"""Algorithm 1 of PFA

This implementation has two specific points in mind:
1. Adjacency Matrix based on arbitrary definition of correlation and
2. No association of X with Y/output is used (not supervised).

There are reasons why these points are not considered in the original
implementations. These reasons are mentioned in the paper.

Particularly, tightly connected dependency graphs are not pruned (as
in test_data0). This does not mean that we cannot prune the nodes
based on redundancy or functional dependency, but rather that such
pruning is not unique and arbitrary removal would suffice. The paper
suggests to study such multiple-node complete subgraphs separately
and/or use the association with the output variable (Y).

"""

import networkx as nx
import numpy as np
import scipy.stats
from itertools import combinations
from random import sample, seed

def test_data0(n=5000):
    # Everything is a function of everything. Nothing gets deleted by PFA.
    # 1 -- 0
    # |    |
    # \   /
    #   2
    A = 5*np.random.rand(n, 3)

    A[:, 1] = 0.6*A[:, 0] # proportional
    A[:, 2] = 0.3*A[:, 0] + 1.5*A[:, 1] # linear combination
    return A

def test_data1(n=5000):
    # Ex 3 from the paper, 0, 1 & 2 are independent
    # 2 -- 3 -- 0
    #      |    |
    #      1 -- 4
    A = 5*np.random.rand(n, 5)

    A[:, 3] = 2*A[:, 0]*A[:, 1]*A[:, 2]
    A[:, 4] = A[:, 0]*A[:, 1]
    return A    

def test_data2(n=5000):
    # Test data from the package: 0 & 1 are independent
    # 2 -- 0 -- 3 -- 1 -- 4
    A=5*np.random.rand(n, 5)

    A[:,2]=A[:,0]*0.01 + 5
    A[:,3]=A[:,0]*A[:,1]**2 # this serves as a bridge between ind islands 0 & 1
    A[:,4]=np.exp(-A[:,1])

    return A

def test_data3(n=5000):
    # Test data from the package: 0 & 1 are independent
    # 2 -- 0
    # 1 -- 3
    # |_ 4_|
    A=5*np.random.rand(n, 5)

    A[:,2]=A[:,0]*0.01 + 5
    A[:,3]=A[:,1]**2
    A[:,4]=np.exp(-A[:,1]) # via 1: 3 -- 4

    return A    

def test_data4(n=5000):
    # Two alternative splits of the graph: at 1 or 0
    # 2 & 0 are independent
    # 2 -- 1 -- 0 -- 3
    #            \__ 4
    A = 5*np.random.rand(n, 5)
    A[:, 2] = A[:, 1]*14 + 0.01
    A[:, 0] = A[:, 1]*A[:, 3]**2 + 10*np.exp(-A[:, 4])

    return A


def ex_cor_fun(x, y, alt='two-sided'):
    """Example of a custom correlation function which will work with
    cor_mat

    """
    return scipy.stats.kendalltau(x, y, variant='c', alternative=alt)

def cor_mat(X, meth="p", **kwargs):
    """Correlation matrix calculation.

    Input:

    X: input data matrix (n_obs x n_feat)

    meth: method for correlation calculation. Predefined options: 'p'
    -- Pearson, 's' -- Spearman, 'k' -- Kendall. These use scipy.stats
    functions pearsonr, spearmanr, and kendalltau,
    respectively. Alternatively, if meth is a callable/function, it
    defines a custom correlation function.

    **kwargs: arguments to the correlation function (see ex_cor_fun in
      this module), including the scipy.stats functions.

    Output:

    C: correlation matrix (n_feat x n_feat), up-triangular only

    P: correlation p-values (n_feat x n_feat), up-triangular only

    """
    n = X.shape[1]
    C = np.zeros((n, n)) # container for cor coef, may be optimized to be sparse
    P = np.ones((n, n)) # container for cor P-val, may be optimized to be sparse
    cmb = combinations(range(n), 2)
    if(hasattr(meth, '__call__')):
        cor_fun = meth
    elif(isinstance(meth, str)):
        if(meth == 'p'):
            cor_fun = scipy.stats.pearsonr
        elif(meth == 's'):
            cor_fun = scipy.stats.spearmanr
        elif(meth == 'k'):
            cor_fun = scipy.stats.kendalltau
        else:
            raise ValueError ("Unknown symbol %s" % meth)
    else:
        raise ValueError("Unknown type of method")
            
    for c in cmb:
        cor, pval = cor_fun(X[:, c[0]], X[:, c[1]], **kwargs)
        C[c[0], c[1]] = cor
        P[c[0], c[1]] = pval

    return C, P

def cor_adj_mat(X, meth='p', alpha=0.05, correct=False, **kwargs):
    """Construct an adjacency matrix from the correlation matrix

    Input:

    X: input data matrix (n_obs x n_feat)

    meth: method for correlation calculation. Predefined options: 'p'
    -- Pearson, 's' -- Spearman, 'k' -- Kendall. These use scipy.stats
    functions pearsonr, spearmanr, and kendalltau,
    respectively. Alternatively, if meth is a callable/function, it
    defines a custom correlation function.

    alpha: correlation test p-value cutoff (default: 0.05)

    correct: whether to correct for multiple tests (default: True)

    **kwargs: arguments to the correlation function (see ex_cor_fun in
      this module), including the scipy.stats functions.

    Output:

    A: boolean adjacency matrix (n_feat x n_feat), up-triangular only

    """
    C, P = cor_mat(X, meth=meth, **kwargs)
    if correct: # simple P-val correction
        n = C.shape[1] # C/P must be square upper triangular
        n_cmb = n*(n-1) / 2
        print("N. comparisons:", str(n_cmb))
        P = P * n_cmb
    return P < alpha

def cor_graph(cor_adj_mat):
    """Construct dependency graph from adjacency matrix.

    Input:

    cor_adj_mat: numpy 2d array of the adjacency matrix. In this
    module, it is a boolean and upper-triangular matrix.

    Output:

    NetworkX graph object of the dependency graph.

    """
    return nx.from_numpy_matrix(cor_adj_mat)

def pfa1_full(X, meth='p', alpha=0.05, correct=True, rnd_seed=None, **kwargs):
    """Core Algorithm 1 of PFA. Full pipelined implementation.

    Input:

    X: input data matrix (n_obs x n_feat)

    meth: method for correlation calculation. Predefined options: 'p'
    -- Pearson, 's' -- Spearman, 'k' -- Kendall. These use scipy.stats
    functions pearsonr, spearmanr, and kendalltau,
    respectively. Alternatively, if meth is a callable/function, it
    defines a custom correlation function.

    alpha: correlation test p-value cutoff (default: 0.05)

    correct: whether to correct for multiple tests (default: True)

    rnd_seed: rnd generator state (default: None, arbitrary)

    **kwargs: arguments to the correlation function (see ex_cor_fun in
      this module), including the scipy.stats functions.

    Output:

    Gs: list of complete subgraphs (NetworkX objects)

    Gs_nodes: list of nodes in each subgraph

    Gs_edges: list of edges (tuples) of each subgraph

    """
    adj = cor_adj_mat(X, meth=meth, alpha=alpha, correct=correct, **kwargs)
    print("Adjacency matrix:")
    print(adj)
    gr = cor_graph(adj)
    subgr, subgr_nodes, subgr_edges = pfa1(gr, rnd_state=rnd_seed)
    return subgr, subgr_nodes, subgr_edges

def pfa1(graph, rnd_state=None):
    """Core Algorithm 1 of PFA with random initialization of the connected
    components (cc).

    Input:

    graph: NetworkX graph object representing dependency graph

    rnd_state: rnd generator seed if reproducibility is required. The
    default (None) uses arbitrary seed.

    Output:

    Gs: list of complete subgraphs (NetworkX objects)

    Gs_nodes: list of nodes in each subgraph

    Gs_edges: list of edges (tuples) of each subgraph

    """
    seed(rnd_state) # seed rnd number generator, if None, then not reproducible
    S = [graph.subgraph(c).copy() for c in nx.connected_components(graph)]
    nS = len(S)
    print("N. cc:", str(nS))
    
    list_graphs_to_divide=[] # list of graphs to divide
    list_complete_sub_graphs=[] # list of complete subgraphs
    list_nodes_complete_sub_graphs=[] # list of lists of nodes corresponding to the complete subgraphs of list_complete_sub_graphs

    # filter non-complete subgraphs
    for i in sample(S, nS): # why sample? order of subgraphs to process is not important
        if list(nx.complement(i).edges)!=[]: # if a graph is not complete
            list_graphs_to_divide.append(i)
        else:
            list_complete_sub_graphs.append(i)
            list_nodes_complete_sub_graphs.append(list(i.nodes))
    n_iter = 1
    # remove nodes from non-complete subgraphs until only complete subgraphs are left

    while list_graphs_to_divide!=[]:
        #print("Iteration: " + str(n_iter), end="\r")
        # any_cluster_dissected=1
        n_graphs_to_divide = len(list_graphs_to_divide)
        # Randomization should be here (?)
        for current_graph in sample(list_graphs_to_divide, n_graphs_to_divide):
            set_nodes_to_delete=nx.minimum_node_cut(current_graph)  # minimum cut algorithm
            print(str(len(set_nodes_to_delete)) + " node(s) removed:")
            print(set_nodes_to_delete)
            print(" from "+str(current_graph.nodes)+" graph nodes")
            list_graphs_to_divide.remove(current_graph) # remove the dissected graph
            for node in list(set_nodes_to_delete):
                current_graph.remove_node(node) # remove the minimum cut nodes
            new_S = [current_graph.subgraph(c).copy() for c in nx.connected_components(current_graph)]
            # Sort the new subgraphs into a list of complete subgraphs and subgraphs that can be further divided
            for sub_graph_of_current_graph in new_S:
                if list(nx.complement(sub_graph_of_current_graph).edges)!=[]:
                    list_graphs_to_divide.append(sub_graph_of_current_graph)
                else:
                    list_complete_sub_graphs.append(sub_graph_of_current_graph)
                    list_nodes_complete_sub_graphs.append(list(sub_graph_of_current_graph.nodes))
        n_iter = n_iter + 1

    print("N. iterations:",str(n_iter-1))
    n = len(list_complete_sub_graphs)
    print("N. subgraphs:", str(n))
    sub_graph_components = [list(x.nodes) for x in list_complete_sub_graphs]
    sub_graph_arch = [list(x.edges) for x in list_complete_sub_graphs]
    return list_complete_sub_graphs, sub_graph_components, sub_graph_arch



if __name__ == "__main__":
    print("===================================================")
    print("Ex. 1: tightly connected graph, nothing gets pruned")
    A = test_data0()
    x, y, z = pfa1_full(A)

    print("Sub graphs:")
    print(y)

    print("===================================================")
    print("Ex. 2: Example 3 from the paper")
    A = test_data1()
    x, y, z = pfa1_full(A)

    print("Sub graphs:")
    print(y)

    print("===================================================")
    print("Ex. 3: Test data from the package, v0 & v1 are fully independent, hierarchy via v3")
    A = test_data2()
    x, y, z = pfa1_full(A)

    print("Sub graphs:")
    print(y)

    print("===================================================")
    print("Ex. 4: As Ex.3, v0 & v1 are fully independent, but v3 is not a bridge, no hierarchy")
    A = test_data3()
    x, y, z = pfa1_full(A)

    print("Sub graphs:")
    print(y)

    print("===================================================")
    print("Ex. 5: Barabasi-Albert preferential attachment graph")
    g = nx.barabasi_albert_graph(100, 3)
    x, y, z = pfa1(g)

    print("Sub graphs:")
    print(y)    
