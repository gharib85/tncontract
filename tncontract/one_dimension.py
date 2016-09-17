import numpy as np
from tncontract.tensor import *

class OneDimensionalTensorNetwork():
    """A one dimensional tensor network specified by a 1D array of tensors (a list or 1D numpy array)
    where each tensor has a left and a right index.
    Need to specify which labels correspond to these using arguments left_label, right_label."""
    def __init__(self, tensors, left_label, right_label):
        self.left_label=left_label
        self.right_label=right_label
        #Copy input tensors to the data attribute
        self.data=np.array([x.copy() for x in tensors])
        #Every tensor will have three indices corresponding to "left", "right" and "phys" labels. 
        #If only two are specified for left and right boundary tensors (for open boundary conditions)
        #an extra dummy index of dimension 1 will be added. 
        for x in self.data:
            if left_label not in x.labels: x.add_dummy_index(left_label)
            if right_label not in x.labels: x.add_dummy_index(right_label)

   #Add container emulation
    def __iter__(self):
        return self.data.__iter__()
    def __len__(self):
        return self.data.__len__()
    def __getitem__(self, key):
        return self.data.__getitem__(key)
    def __setitem__(self, key, value):
        self.data.__setitem__(key, value)

    def copy(self):
        """Alternative the standard copy method, returning a
        OneDimensionalTensorNetwork that is not
        linked in memory to the previous ones."""
        return OneDimensionalTensorNetwork([x.copy() for x in self], self.left_label, self.right_label)

    def reverse(self):
        self.data=self.data[::-1]
        temp=self.left_label
        self.left_label=self.right_label
        self.right_label=temp

class MatrixProductState(OneDimensionalTensorNetwork):
    """Matrix product state"is a list of tensors, each having and index labelled "phys" 
    and at least one of the indices "left", "right"
    Input is a list of tensors, with three up to three index labels, If the labels aren't already 
    specified as "left", "right", "phys" need to specify which labels correspond to these using 
    arguments left_label, right_label, phys_label. 
    The tensors input will be copied, and will not point in memory to the original ones."""
        
    def __init__(self, tensors, left_label, right_label, phys_label):
        OneDimensionalTensorNetwork.__init__(self, tensors, left_label, right_label)
        self.phys_label=phys_label

    def copy(self):
        """Replaces the standard copy method, returning an MPS of tensors that aren't linked in memory to the 
        previous ones."""
        return MatrixProductState([x.copy() for x in self], self.left_label, self.right_label, self.phys_label)

    def left_canonise(self, start=0, end=-1, chi=0, threshold=10**-14, normalise=False, partial_normalise=True):
        """Perform left canonisation. Start and end specify the interval which will be left
        canonised. If start and end aren't specified, the MPS will be 
        put in left canonical form. end=-1 means until the end of chain. 
        If partial_normalise=True, then on canonising a small part of the chain, each S matrix obtained 
        during SVDs will be divided by the largest eigenvalue of S.
        """
        N=len(self)
        if end==-1:
            end=N

        #At each step will divide by a constant so that the largest singular value of S is 1
        #Will store the product of these constants in variable "norm"
        norm=1
        for i in range(start,end):
            if i==N-1:
                #The final SVD has no right index, so S and V are just scalars. S is the norm of the state. 
                if normalise==True:
                    self[i].data=self[i].data/np.linalg.norm(self[i].data)
                else:
                    self[i].data=self[i].data*norm
                return
            else:
                U,S,V = tensor_svd(self[i], [self.phys_label, self.left_label])

            #Truncate to threshold and to specified chi
            #Normalise S
            #TODO something wrong with the norm (gives wrong answer)
            singular_values=np.diag(S.data)
            largest_singular_value=singular_values[0]
            singular_values=singular_values/largest_singular_value
            norm*=largest_singular_value

            singular_values_to_keep = singular_values[singular_values > threshold]
            if chi:
                singular_values_to_keep = singular_values_to_keep[:chi]
            S.data=np.diag(singular_values_to_keep)
            #Truncate corresponding singular index of U and V
            U.data=U.data[:,:,0:len(singular_values_to_keep)]
            V.data=V.data[0:len(singular_values_to_keep)]

            U.replace_label("svd_in", self.right_label)
            self[i]=U
            self[i+1]=contract(V, self[i+1], self.right_label, self.left_label)
            self[i+1]=contract(S, self[i+1], ["svd_in"], ["svd_out"])
            self[i+1].replace_label("svd_out", self.left_label)

            #Reabsorb normalisation factors into next tensor
            #If partial_normalise is True, this is not done
            #Note if i==N-1 (end of chain), this will not be reached 
            #and normalisation factors will be taken care of in the earlier block.
            if i==end-1:
                if not partial_normalise:
                    self[i+1].data*=norm

    def right_canonise(self, start=0, end=-1, chi=0, threshold=10**-14, normalise=False, partial_normalise=False):
        """Perform right canonisation. Start and end specify the interval which will be left
        canonised. If start and end aren't specified, the MPS will be 
        put in left canonical form. end=-1 means until the end of chain. 
        If partial_normalise=True, then on canonising a small part of the chain, each S matrix obtained 
        during SVDs will be divided by the largest eigenvalue of S.
        """
        self.reverse()
        N=len(self)
        if end==-1:
            end=N
        self.left_canonise(start=N-end, end=N-start, chi=0, threshold=threshold, normalise=normalise, 
                partial_normalise=partial_normalise)
        self.reverse()

    def replace_left_right_phys_labels(self, new_left_label=None, new_right_label=None, new_phys_label=None):
        """
        Replace left, right, phys labels in every tensor, and update the MatrixProductState attributes
        left_label, right_label and phys_label. If new label is None, the label will not be replaced. 
        """
        old_labels=[self.left_label, self.right_label, self.phys_label]
        new_labels=[new_left_label, new_right_label, new_phys_label]
        #Replace None entries with old label (i.e. don't replace)
        for i, x in enumerate(new_labels):
            if x==None:
                new_labels[i]=old_labels[i]
        for tensor in self.data:
            tensor.replace_label(old_labels, new_labels)

        self.left_label=new_left_label
        self.right_label=new_right_label
        self.phys_label=new_phys_label

    def standard_labels(self, suffix=""):
        """
        Overwrite self.labels, self.left_label, self.right_label, self.phys_label
        with standard labels "left", "right", "phys"
        """
        self.replace_left_right_phys_labels(new_left_label="left"+suffix, new_right_label="right"+suffix, 
                new_phys_label="phys"+suffix)

    def check_canonical_form(self, threshold=10**-14, print_output=True):
        """Determines which tensors in the MPS are left canonised, and which are right canonised.
        Returns the index of the first tensor (starting from left) that is not left canonised, 
        and the first tensor (starting from right) that is not right canonised. If print_output=True,
        will print useful information concerning whether a given MPS is in a canonical form (left, right, mixed).""" 
        mps_cc=mps_complex_conjugate(self)
        first_site_not_left_canonised=len(self)-1
        for i in range(len(self)-1): 
            I=contract(self[i], mps_cc[i], [self.phys_label, self.left_label], [mps_cc.phys_label, mps_cc.left_label])
            #Check if tensor is left canonised.
            if np.linalg.norm(I.data-np.identity(I.data.shape[0])) > threshold:
                first_site_not_left_canonised=i
                break
        first_site_not_right_canonised=0
        for i in range(len(self)-1,0, -1): 
            I=contract(self[i], mps_cc[i], [self.phys_label, self.right_label], [mps_cc.phys_label, mps_cc.right_label])
            #Check if tensor is right canonised.
            right_canonised_sites=[]
            if np.linalg.norm(I.data-np.identity(I.data.shape[0])) > threshold:
                first_site_not_right_canonised=i
                break
        if print_output:
            if first_site_not_left_canonised==first_site_not_right_canonised:
                if first_site_not_left_canonised==len(self)-1:
                    if abs(np.linalg.norm(self[-1].data)-1) > threshold:
                        print("MPS in left canonical form (unnormalised)")
                    else:
                        print("MPS in left canonical form (normalised)")
                elif first_site_not_left_canonised==0:
                    if abs(np.linalg.norm(self[0].data)-1) > threshold:
                        print("MPS in right canonical form (unnormalised)")
                    else:
                        print("MPS in right canonical form (normalised)")
                else:
                    print("MPS in mixed canonical form with orthogonality centre at site "+str(first_site_not_right_canonised))
            else:
                if first_site_not_left_canonised==0:
                    print("No tensors left canonised")
                else:
                    print("Tensors left canonised up to site "+str(first_site_not_left_canonised))
                if first_site_not_right_canonised==len(self)-1:
                    print("No tensors right canonised")
                else:
                    print("Tensors right canonised up to site "+str(first_site_not_right_canonised))
        return (first_site_not_left_canonised, first_site_not_right_canonised)


class MatrixProductOperator(OneDimensionalTensorNetwork):
    #TODO currently assumes open boundaries
    """Matrix product operator "is a list of tensors, each having and index labelled "phys" 
    and at least one of the indices "left", "right"
    Input is a list of tensors, with three up to three index labels, If the labels aren't already 
    specified as "left", "right", "physin", "physout" need to specify which labels correspond to these using 
    arguments left_label, right_label, physin_label and physout_label. """
    def __init__(self, tensors, left_label, right_label, physout_label, physin_label):
        OneDimensionalTensorNetwork.__init__(self, tensors, left_label, right_label)
        self.physout_label=physout_label
        self.physin_label=physin_label

    ###TODO replace copy method

def contract_multi_index_tensor_with_one_dim_array(tensor, array, label1, label2):
    """Will contract a one dimensional tensor array of length N 
    with a single tensor with N indices with label1.
    All virtual indices are also contracted. 
    Each tensor in array is assumed to have an index with label2. 
    Starting from the left, the label2 index of each tensor 
    is contracted with the first uncontracted label1 index of tensor
    until every tensor in array is incorporated.
    It is assumed that only the indices to be contracted have the labels label1 
    label2."""

    #To avoid possible label conflicts, rename labels temporarily 
    temp_label=0 
    tensor.replace_label(label1, temp_label)

    C=contract(tensor, array[0], temp_label, label2, index_list1=[0])
    for i in range(1, len(array)):
        #TODO make this work
        C=contract(C, array[i], [array.right_label, temp_label], [array.left_label, label2], index_list1=[0,1])

    #Contract boundaries of array
    C.contract_internal(array.right_label, array.left_label)
    #Restore original labelling to tensor
    tensor.replace_label(temp_label, label1)
    return C

def contract_virtual_indices(array_1d):
    C=array_1d[0]
    for x in array_1d[1:]:
        C=contract(C, x, array_1d.right_label, array_1d.left_label)
    #Contract left and right boundary indices (periodic boundaries)
    #For open boundaries, these will have dimension 1 and therefore will simply
    #be removed
    C.contract_internal(array_1d.right_label, array_1d.left_label) 
    return C
 
def left_canonical_form_mps(orig_mps, chi=0, threshold=10**-14, normalise=False):
    """Computes left canonical form of an MPS using algorithm in Schollwock 2011, 
    by taking successive SVDs.
    Compression is usually not done at this stage, but it can by specifying the optional chi argument.
    Setting chi=0 means no compression."""
    """Possible to speed up using a QR rather than SVD decomposition"""
    mps=orig_mps.copy()
    mps.left_canonise(chi=chi, threshold=threshold, normalise=normalise)
    return mps

def reverse_mps(mps):
    return MatrixProductState([x.copy() for x in reversed(mps)], mps.right_label, mps.left_label, mps.phys_label)

def right_canonical_form_mps(orig_mps, chi=0, threshold=10**-14, normalise=False):
    """Identical to left canonical form but starting from right"""
    #TODO replace with call to right canonise method
    #mps=[x.copy() for x in orig_mps] #Dont want to modify the original mps
    mps=reverse_mps(orig_mps)
    mps=left_canonical_form_mps(mps, chi=chi, threshold=threshold, normalise=normalise)
    return reverse_mps(mps)

def check_canonical_form_mps(mps, threshold=10**-14, print_output=True):
    """Determines which tensors in the MPS are left canonised, and which are right canonised.
    Returns the index of the first tensor (starting from left) that is not left canonised, 
    and the first tensor (starting from right) that is not right canonised. If print_output=True,
    will print useful information concerning whether a given MPS is in a canonical form (left, right, mixed).""" 
    mps_cc=mps_complex_conjugate(mps)
    first_site_not_left_canonised=len(mps)-1
    for i in range(len(mps)-1): 
        I=contract(mps[i], mps_cc[i], [mps.phys_label, mps.left_label], [mps_cc.phys_label, mps_cc.left_label])
        #Check if tensor is left canonised.
        if np.linalg.norm(I.data-np.identity(I.data.shape[0])) > threshold:
            first_site_not_left_canonised=i
            break
    first_site_not_right_canonised=0
    for i in range(len(mps)-1,0, -1): 
        I=contract(mps[i], mps_cc[i], [mps.phys_label, mps.right_label], [mps_cc.phys_label, mps_cc.right_label])
        #Check if tensor is right canonised.
        right_canonised_sites=[]
        if np.linalg.norm(I.data-np.identity(I.data.shape[0])) > threshold:
            first_site_not_right_canonised=i
            break
    if print_output:
        if first_site_not_left_canonised==first_site_not_right_canonised:
            if first_site_not_left_canonised==len(mps)-1:
                if abs(np.linalg.norm(mps[-1].data)-1) > threshold:
                    print("MPS in left canonical form (unnormalised)")
                else:
                    print("MPS in left canonical form (normalised)")
            elif first_site_not_left_canonised==0:
                if abs(np.linalg.norm(mps[0].data)-1) > threshold:
                    print("MPS in right canonical form (unnormalised)")
                else:
                    print("MPS in right canonical form (normalised)")
            else:
                print("MPS in mixed canonical form with orthogonality centre at site "+str(first_site_not_right_canonised))
        else:
            if first_site_not_left_canonised==0:
                print("No tensors left canonised")
            else:
                print("Tensors left canonised up to site "+str(first_site_not_left_canonised))
            if first_site_not_right_canonised==len(mps)-1:
                print("No tensors right canonised")
            else:
                print("Tensors right canonised up to site "+str(first_site_not_right_canonised))
    return (first_site_not_left_canonised, first_site_not_right_canonised)

def svd_compress_mps(orig_mps, chi, threshold=10**-15, normalise=False):
    """Simply right canonise the left canonical form according to Schollwock"""
    mps=left_canonical_form_mps(orig_mps, threshold=threshold, normalise=normalise)
    return right_canonical_form_mps(mps, chi=chi, threshold=threshold, normalise=normalise)

def variational_compress_mps(mps, chi, max_iter=20):
    #TODO I think I have implemented this very inefficiently. Fix.
    """Take an mps represented as a list of tensors with labels: left, right, phys
    and return an mps in the same form with bond dimension chi. (using dmrg)"""
    #TODO check check frob norm difference to previous iteration and stop when the update becomes too small. 
    #First make a guess at optimal form using svd_truncate_mps, as above.
    n=len(mps)

    #Start with a good guess for the new mps, using the canonical form
    new_mps=svd_compress_mps(mps, chi, threshold=10**-15, normalise=False)

    #Loop along the chain from left to right, optimizing each tensor 
    for k in range(max_iter):
        for i in range(n):
            #Define complex conjugate of mps
            new_mps_cc=[x.copy() for x in new_mps]
            for x in new_mps_cc:
                x.conjugate()
                x.replace_label("left", "left_cc")
                x.replace_label("right", "right_cc")

            #Computing A (quadratic component)

            #Right contraction
            if i!=n-1:
                right_boundary=contract(new_mps[-1], new_mps_cc[-1], ["phys"], ["phys"] )
                for j in range(n-2, i, -1):
                    right_boundary=contract(right_boundary, new_mps[j], ["left"], ["right"])
                    right_boundary=contract(right_boundary, new_mps_cc[j], ["left_cc", "phys"], ["right_cc", "phys"])

            #Left contraction
            if i!=0:
                left_boundary=contract(new_mps[0], new_mps_cc[0], ["phys"], ["phys"] )
                for j in range(1,i):
                    left_boundary=contract(left_boundary, new_mps[j], ["right"], ["left"])
                    left_boundary=contract(left_boundary, new_mps_cc[j], ["right_cc", "phys"], ["left_cc", "phys"])

            #Combine left and right components to form A

            #Dimension of the physical index
            phys_index=new_mps[i].labels.index("phys")
            phys_index_dim=new_mps[i].data.shape[phys_index]
            I_phys=Tensor(data=np.identity(phys_index_dim), labels=["phys_cc", "phys"])
            #Define the A matrix
            if i==0:
                A=tensor_product(right_boundary, I_phys)
            elif i==n-1:
                A=tensor_product(left_boundary, I_phys)
            else:
                A=tensor_product(left_boundary, right_boundary)
                A=tensor_product(A, I_phys)

            #Compute linear component "b"
            #Right contraction
            if i!=n-1:
                right_boundary=contract(mps[-1], new_mps_cc[-1], ["phys"], ["phys"] )
                for j in range(n-2, i, -1):
                    right_boundary=contract(right_boundary, mps[j], ["left"], ["right"])
                    right_boundary=contract(right_boundary, new_mps_cc[j], ["left_cc", "phys"], ["right_cc", "phys"])
            #Left contraction
            if i!=0:
                left_boundary=contract(mps[0], new_mps_cc[0], ["phys"], ["phys"] )
                for j in range(1,i):
                    left_boundary=contract(left_boundary, mps[j], ["right"], ["left"])
                    left_boundary=contract(left_boundary, new_mps_cc[j], ["right_cc", "phys"], ["left_cc", "phys"])

            #Connect left and right boundaries to form b
            if i==0:
                b=contract(mps[0], right_boundary, ["right"], ["left"])
            elif i==n-1:
                b=contract(left_boundary, mps[-1], ["right"], ["left"])
            else:
                b=contract(left_boundary, mps[i], ["right"], ["left"])
                b=contract(b, right_boundary, ["right"], ["left"])

            #Put indices in correct order, convert to matrices, and solve linear equation
            if i==0:
                #row indices
                A.move_index("left_cc", 0)
                A.move_index("phys_cc", 1)
                #column indices
                A.move_index("left", 2)
                A.move_index("phys", 3)
                old_shape=A.data.shape
                A_matrix=np.reshape(A.data, (np.prod(old_shape[0:2]),np.prod(old_shape[2:4])))

                b.move_index("left_cc", 0)
                b_vector=b.data.flatten()
                minimum=np.linalg.solve(A_matrix, b_vector)
                updated_tensor=Tensor(data=np.reshape(minimum, (old_shape[0], old_shape[1])), labels=["right", "phys"])
            elif i==n-1:
                A.move_index("right_cc", 0)
                A.move_index("phys_cc", 1)
                A.move_index("right", 2)
                A.move_index("phys", 3)
                old_shape=A.data.shape
                A_matrix=np.reshape(A.data, (np.prod(old_shape[0:2]),np.prod(old_shape[2:4])))

                b.move_index("right_cc", 0)
                b_vector=b.data.flatten()
                minimum=np.linalg.solve(A_matrix, b_vector)

                updated_tensor=Tensor(data=np.reshape(minimum, (old_shape[0], old_shape[1])), labels=["left", "phys"])
            else:
                A.move_index("right_cc", 0)
                A.move_index("left_cc", 1)
                A.move_index("phys_cc", 2)
                A.move_index("right", 3)
                A.move_index("left", 4)
                A.move_index("phys", 5)
                old_shape=A.data.shape
                A_matrix=np.reshape(A.data, (np.prod(old_shape[0:3]),np.prod(old_shape[3:6])))

                b.move_index("right_cc", 0)
                b.move_index("left_cc", 1)
                b_vector=b.data.flatten()
                minimum=np.linalg.solve(A_matrix, b_vector)

                updated_tensor=Tensor(data=np.reshape(minimum, (old_shape[0], old_shape[1], old_shape[2])), 
                        labels=["left", "right", "phys"])
                updated_tensor.consolidate_indices()
            new_mps[i]=updated_tensor

    return new_mps

def mps_complex_conjugate(mps):
    """Will take complex conjugate of every entry of every tensor in mps, 
    and append label_suffix to every label"""
    new_mps=mps.copy()
    for x in new_mps.data: 
        x.conjugate()
    return new_mps

def inner_product_one_dimension(array1, array2, label1, label2):
    """"""
    pass

def inner_product_mps(mps_bra, mps_ket, complex_conjugate_bra=True, return_whole_tensor=False):
    """Inner product of two mps.
    They must have the same physical index dimensions"""
    if complex_conjugate_bra:
        mps_bra_cc=mps_complex_conjugate(mps_bra)
    else:
        #Just copy without taking complex conjugate
        mps_bra_cc=mps_bra.copy()

    #Temporarily relabel so no conflicts 
    mps_ket_old_labels=[mps_ket.left_label, mps_ket.right_label, mps_ket.phys_label]
    mps_ket.standard_labels()
    mps_bra_cc.standard_labels(suffix="_cc") #Suffix to distinguish from mps_ket labels

    left_boundary=contract(mps_bra_cc[0], mps_ket[0], mps_bra_cc.phys_label, mps_ket.phys_label)
    for i in range(1,len(mps_ket)):
        left_boundary=contract(left_boundary, mps_bra_cc[i], mps_bra_cc.right_label, mps_bra_cc.left_label)
        left_boundary=contract(left_boundary, mps_ket[i], [mps_ket.right_label, mps_bra_cc.phys_label], [mps_ket.left_label, mps_ket.phys_label])

    #Restore labels of mps_ket
    mps_ket.replace_left_right_phys_labels(new_left_label=mps_ket_old_labels[0], new_right_label=mps_ket_old_labels[1],
            new_phys_label=mps_ket_old_labels[2])

    left_boundary.remove_all_dummy_indices()
    if return_whole_tensor:
        return left_boundary
    else:
        return left_boundary.data

def frob_distance_squared(mps1, mps2):
    ip=inner_product_mps
    return ip(mps1, mps1) + ip(mps2, mps2) - 2*np.real(ip(mps1, mps2))

def contract_mps_mpo(mps, mpo):
    """Will contract the physical index of mps with the physin index of mpo.
    Left and right indices will be combined. 
    The resulting MPS will have the same left and right labels as mps and the physical label will be
    mpo.physout_label"""
    N=len(mps)
    new_mps=[]
    for i in range(N):
        new_tensor=contract(mps[i], mpo[i], mps.phys_label, mpo.physin_label)
        new_tensor.consolidate_indices()
        new_mps.append(new_tensor)
    new_mps=MatrixProductState(new_mps, mps.left_label, mps.right_label, mpo.physout_label)
    return new_mps

