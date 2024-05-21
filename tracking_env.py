#!/usr/bin/env python

"""
Deep reinforcement learning tractography environment

Author: Bryson Gray
2024
"""

import numpy as np
import torch
import scipy
from skimage.draw import line_nd
from skimage.filters import gaussian
from image import Image


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def density_error_change(true_density, old_density, new_density):
    """ Change in the error between true and estimated density maps. Error is mean absolute difference between density maps
        after normalizing by their sums.

        Parameters
        ----------
        true_density : torch.Tensor
        old_density: torch.Tensor
        new_density: torch.Tensor
        
        Returns
        -------
        error_change : scalar
    
    """
    # true_density = true_density / (true_density.sum() + np.finfo(float).eps)
    # old_density = old_density / (old_density.sum() + np.finfo(float).eps)
    # new_density = new_density / (new_density.sum() + np.finfo(float).eps)

    # old_mad = torch.mean(torch.abs(true_density - old_density))
    # new_mad = torch.mean(torch.abs(true_density - new_density))

    # TODO: test using sum of square error instead of mean absolute difference
    old = torch.sum((old_density - true_density)**2)
    new = torch.sum((new_density - true_density)**2)

    return new - old


class Environment():
    """ Loads a volume. Takes a list of seeds which
    which will be cycled through on every call of reset.

    Parameters
    ----------
    img : torch.Tensor
        The image to perform tracking on. Tensor with shape c x h x w x d.
    radius : int
        The radius of a state input image patch along each axis (total width is 2*radius + 1).
    seeds : ndarray
        N x 3 array of starting streamline coordinates
    mask : torch.Tensor
        Mask of the true neuron. Tensor  with shape 1 x h x w x d.
    true_denstiy : torch.Tensor
        True neuron position as a density. Tensor with shape 1 x h x w x d
    actions : ndarray
        N x 3 array of possible step directions.
    step_size : float
        Distance taken in each step in units of pixels.
    max_len : int
        Maximum number of steps allowed per streamline
    alpha : float
        Density matching weight
    beta : float
        Smoothness weight
    
    Attributes
    ----------
    head_id : int
        Index of the current streamline head out of the whole tracking bundle.
    img : torch.Tensor
        Tensor with shape c x h x w x d where the first channels are the input image and the last channel is the streamline density.
    radius : int
        The radius of a state input image patch along each axis (total width is 2*radius + 1).
    paths : torch.Tensor
        Tensor with shape t x N x 3, where t is the length of the streamlines.
    mask : torch.Tensor
        Mask of the true neuron. Tensor  with shape 1 x h x w x d.
    true_denstiy : torch.Tensor
        True neuron position as a density. Tensor with shape 1 x h x w x d
    action_space : torch.Tensor
        N x 3 tensor of possible step directions.
    step_size : float
        Distance taken in each step in units of pixels.
    max_len : int
        Maximum number of steps allowed per streamline
    n_resets : int
        Count of the number of episode resets during training.

    """

    def __init__(self, img, radius, seeds, mask, true_density, branch_points, terminals, actions,\
                 n_seeds=1, step_size=1.0, step_width=1.0, max_len=10000, alpha=1.0, beta=1e-3, friction=1e-4):

        self.head_id = 0
        self.n_resets = 0 # count number of resets
        self.img = Image(img)
        self.radius = radius
        self.seeds = seeds        
        self.mask = mask
        self.true_density = Image(true_density)
        self.branch_points = branch_points
        self.terminals = terminals
        # make copies of the branch and terminal points so these can be changed while saving the originals
        self.branch_points_copy = self.branch_points.clone()
        self.terminals_copy = self.terminals.clone()
        self.n_seeds = n_seeds # the number of paths per bundle
        self.step_size = step_size
        self.step_width = step_width
        self.max_len = max_len
        self.action_space = actions
        if not isinstance(self.action_space, torch.Tensor):
            self.action_space = torch.tensor(self.action_space)

        seed_id = self.n_resets % len(self.seeds)
        center = torch.Tensor(self.seeds[seed_id])
        self.r = 4.0 # radius around center to randomly place starting points
        g = torch.Generator()
        g.manual_seed(0)
        offsets = torch.rand((self.n_seeds, 3), generator=g)
        offsets /= torch.sum(offsets**2, dim=1)**0.5
        r = self.r * torch.rand(1)
        bundle_seeds = center[None] + r * offsets

        self.paths = [*torch.Tensor(bundle_seeds)[:,None]] # a list of N paths. each path is a 1 x 3 tensor
        self.alpha = alpha
        self.beta = beta
        self.friction = friction

        # initialize last two step directions randomly for each streamline
        g = torch.Generator()
        g.manual_seed(self.n_resets)
        last_steps = [*2*torch.rand(((len(self.paths),)+(1,3)), generator=g)-1.0] # list of len N paths, of 1x3 tensors
        last_steps = [x / np.sqrt(x[0,0]**2+x[0,1]**2+x[0,2]**2) for x in last_steps] # unit normalize directions
        self.paths = [torch.cat((point - 2*step*self.step_size, point - step*self.step_size, point)) for point, step in zip(self.paths, last_steps)]

        # we will want to save completed paths
        self.finished_paths = []

        # initialize bundle density map
        self.bundle_density = torch.zeros_like(true_density)

        # self.img.data = torch.cat((self.img.data, torch.zeros((3,)+self.img.data.shape[1:])), dim=0) # add 3 channels for path, bifurcation points, and terminal points
        # self.img.data = torch.cat((self.img.data, torch.zeros((2,)+self.img.data.shape[1:])), dim=0) # add 2 channels for path, and bifurcation points.
        self.img.data = torch.cat((self.img.data, torch.zeros((1,)+self.img.data.shape[1:])), dim=0) # add 1 channel for path #TODO: changed for testing
        self.bundle_density = Image(self.bundle_density)
        for i in range(len(self.paths)):
            # add_bundle_point(bundle_density, self.paths[i][0], self.ball)
            for j in range(len(self.paths[i])-1):
                segment = torch.stack((self.paths[i][j], self.paths[i][j+1]), dim=0)
                self.img.draw_line_segment(segment, width=0, channel=3)
                self.bundle_density.draw_line_segment(segment, width=self.step_width)


    def get_state(self):
        """ Get the state for the current step at streamline 'head_id'. The state consists of an image patch and
        streamline density patch centered on the streamline head plus the last three streamline positions.

        Returns
        -------
        patch : torch.Tensor
            Tensor with shape (n x c x h x w x d) where the first channels are the input image and the last channel is the streamline density.
        last_steps : torch.Tensor
         Tensor with shape 3 x 3 (3 step positions by 3 euclidean coordinates)
        """
        patch, _ = self.img.crop(self.paths[self.head_id][-1], self.radius, pad=True, value=0.0)
        patch = patch.detach().clone()
        
        last_steps = self.paths[self.head_id][-2:].detach().clone() # 2 x 3 tensor of last three streamline positions

        return patch[None], last_steps[None]


    def get_reward(self, terminate_dist=None, delta_density_diff=None, bifurcate_dist=None, verbose=False, sigmaf=1.0, sigmab=0.3):
        """ Get the reward for the current state. The reward depends on the streamline smoothness and
        the change in distance between the streamline density and true denisty maps.

        Parameters
        ----------
        terminated : bool
        delta_density_diff : float
            Change in median absolute difference between bundle density and true density patch before and after taking a step.
        verbose : bool
            If true, print the values of each term of the reward. 
            
        Returns
        -------
        reward : torch.Tensor
            Tensor with shape 1
        """
        # get_reward should receive one and only one of either terminated, bifurcate, or delta_density_diff
        check = sum([terminate_dist is not None, delta_density_diff is not None, bifurcate_dist is not None])
        if check != 1:
            raise RuntimeError("Function get_reward should receive one and only one of either terminated, bifurcate, or delta_density_diff parameters.")
        
        w = 2.0
        
        if terminate_dist is not None:
            reward = max(-2/self.radius * terminate_dist + 1, -1) * w
            if verbose:
                print(f'terminate distance: {terminate_dist}',
                      f'terminate reward: {reward}')
        
        elif bifurcate_dist is not None:
            reward = max(-2/self.radius * bifurcate_dist + 1, -1) * w
            if verbose:
                print(f'bifurcate distance: {bifurcate_dist}',
                      f'bifurcate reward: {reward}')

        else:
            # prev_step = (self.paths[self.head_id][-2]-self.paths[self.head_id][-3]) / self.step_size
            # current_step = (self.paths[self.head_id][-1]-self.paths[self.head_id][-2]) / self.step_size
            # cos_angle = torch.dot(current_step, prev_step).to(float)
            # note that delta density difference is a change in error,
            # so negative change is good, hence the flipped (positive) exponent which is normally negative for sigmoid function.
            # it is also shifted down so that zero change yields zero.
            #TODO: test using matchin sse
            # m = -2.5e3 #-52631.
            # b = 0.2 #-0.05263
            # diff = m*delta_density_diff + b
            M = -delta_density_diff
            # reward = self.alpha*diff + self.beta*(cos_angle-1) - self.friction
            q = self.paths[self.head_id][-1]
            q_ = self.paths[self.head_id][-2]
            q__ = self.paths[self.head_id][-3]
            # Z = torch.sum((q - 1/(1/sigmaf**2 + 1/sigmab**2)*(q_/sigmaf**2 + (2*q_ - q__)/sigmab**2))**2) * (1/sigmaf**2 + 1/sigmab**2)
            P = - torch.sum((q - q_)**2)/(2*sigmaf**2) - torch.sum((q - 2*q_ + q__)**2) / (2*sigmab**2) # prior likelihood
            reward = self.alpha*M + self.beta*P + 4.0
            if verbose:
                print(f'delta_sse: {delta_density_diff}\n',
                      f'matching reward: {self.alpha*M}\n',
                      f'prior likelihood: {P}\n',
                      f'prior reward: {self.beta*P}')
                    #   f'cos_angle: {cos_angle}','\n',
                    #   f'smoothing reward: {self.beta*(cos_angle-1)}', '\n',
                    #   f'friction reward: {-self.friction}')

        return torch.tensor([reward], device=DEVICE, dtype=torch.float32)


    def step(self, action_id, verbose=False):
        """ Take a tracking step for one streamline. Add the new position to the path
        and the bundle density mask, and compute the reward and new state observation.

        Parameters
        ----------
        action_id : int
            Action index
        
        Returns
        -------
        observation : tuple
            The img patch centered at the new streamline head (a tensor with shape c x h x w x d), and the
            last three streamline positions.
        reward : torch.Tensor
            Tensor with shape 1
        terminated : bool

        """
        terminate_path = False
        accidental_terminate = False # terminating a path for exiting the image boundary should not receive any reward
        terminated = False

        # check if the agent chose to mark the position as a bifurcation point
        # Add the last segment (last two points) from the current path to a new path in the paths list
        if action_id == len(self.action_space)+1: # bifurcate
            self.paths.append(self.paths[self.head_id][-2:])
            # draw point in bifurcation points channel
            self.img.draw_point(self.paths[self.head_id][-1], radius=3, channel=4)

            # compute reward based on distance from nearest true bifurcation point
            diffs = self.branch_points_copy - self.paths[self.head_id][-1][None]
            sq_dists = torch.einsum('ij,ij->i', diffs, diffs)
            min_dist = torch.sqrt(torch.min(sq_dists))

            # if the agent correctly labels a branch point, remove that point from the list.
            if min_dist <= self.radius: # this threshold is chosen arbitrarily
                # remove closest branch point
                # TODO: what happens when all the points are correcly labelled?
                self.branch_points_copy = torch.cat((self.branch_points_copy[:torch.argmin(sq_dists)], self.branch_points_copy[torch.argmin(sq_dists)+1:]))

            reward = self.get_reward(bifurcate_dist=min_dist, verbose=verbose)
            observation = self.get_state()
            # don't move to the new path head until after taking a step on the current path
            
        # check if the action is terminate path
        elif action_id == len(self.action_space):
            terminate_path = True
        else:
            direction = self.action_space[action_id]
            new_position = self.paths[self.head_id][-1] + self.step_size*direction

            # decide if path terminates accidentally
            out_of_bound = any([x >= y or x < 0 for x,y in zip(torch.round(new_position), self.img.data.shape[1:])])
            if out_of_bound:
                terminate_path = True
            else:
                out_of_mask = 1 - self.mask[(0,)+tuple([int(np.round(x)) for x in new_position])]
                too_long = len(self.paths[self.head_id]) > self.max_len
                terminate_path = too_long or out_of_mask

            accidental_terminate = terminate_path

        if terminate_path:
            observation = None

            if accidental_terminate:
                reward = torch.tensor([0.], device=DEVICE)
            else:
                # # compute reward based on distance from nearest terminal point
                # diffs = self.terminals_copy - self.paths[self.head_id][-1][None]
                # sq_dists = torch.einsum('ij,ij->i', diffs, diffs)
                # min_dist = torch.sqrt(torch.min(sq_dists))
                # # if the agent correctly labels a terminal point, remove that point from the list.
                # if min_dist <= self.radius: # this threshold is chosen arbitrarily
                #     # remove closest branch point
                #     self.terminals_copy = torch.cat((self.terminals_copy[:torch.argmin(sq_dists)], self.terminals_copy[torch.argmin(sq_dists)+1:]))
                # reward = self.get_reward(terminate_dist=min_dist, verbose=verbose)
                reward = torch.tensor([0.], device=DEVICE) # turn off terminate reward calculation

            # remove the path from 'paths' and add it to 'ended_paths'
            self.finished_paths.append(self.paths.pop(self.head_id))
            # if that was the last path in the list, then terminate the episode
            if len(self.paths) == 0:
                terminated = True
            # otherwise, move to the next path
            else:
                self.head_id = (self.head_id + 1)%len(self.paths)

        elif action_id < len(self.action_space):
            # add new position to path
            self.paths[self.head_id] = torch.cat((self.paths[self.head_id], new_position[None]))

            # get true density
            center = self.paths[self.head_id][-2]
            r = self.radius + int(np.ceil(self.step_size))
            true_density_patch, _ = self.true_density.crop(center, radius=r) # patch centered at previous step position
            
            # get old patch centered on old streamline head
            old_density_patch, _ = self.bundle_density.crop(center, radius=r)
            old_density_patch = old_density_patch.clone() # need to make a copy or else this will be modified by adding a point to img

            # draw the segment
            segment = self.paths[self.head_id][-2:, :3]
            self.img.draw_line_segment(segment, width=0, channel=3)
            self.bundle_density.draw_line_segment(segment, width=self.step_width)

            # get the new patch centered on the old streamline head
            new_density_patch, _ = self.bundle_density.crop(center, radius=r)

            # find the change in error mean(|true - new|) - mean(|true - old|)
            delta_density_diff = density_error_change(true_density_patch, old_density_patch, new_density_patch)
            reward = self.get_reward(delta_density_diff=delta_density_diff, verbose=verbose)
            observation = self.get_state()

            self.head_id = (self.head_id + 1)%len(self.paths)

        return observation, reward, terminated


    def reset(self):
        # reset the bundle with new random previous step directions.
        self.n_resets += 1

        # start with next seed point
        seed_id = self.n_resets % len(self.seeds)
        center = torch.Tensor(self.seeds[seed_id])
        self.r = 5.0 # radius around center to randomly place starting points
        g = torch.Generator()
        g.manual_seed(0)
        offsets = torch.rand((self.n_seeds, 3), generator=g)
        offsets /= torch.sum(offsets**2, dim=1)**0.5
        r = self.r * torch.rand(1)
        bundle_seeds = center[None] + r * offsets

        self.paths = [*torch.Tensor(bundle_seeds)[:,None]] # a list of N paths. each path is a 1 x 3 tensor

        # initialize last two step directions randomly for each streamline
        g = torch.Generator()
        g.manual_seed(self.n_resets)
        last_steps = [*2*torch.rand(((len(self.paths),)+(1,3)), generator=g)-1.0] # list of len N paths, of 1x3 tensors
        last_steps = [x / np.sqrt(x[0,0]**2+x[0,1]**2+x[0,2]**2) for x in last_steps] # unit normalize directions
        self.paths = [torch.cat((point - 2*step*self.step_size, point - step*self.step_size, point)) for point, step in zip(self.paths, last_steps)]
        self.head_id = 0
        self.finished_paths = []

        # reset branch and terminal points
        self.branch_points_copy = self.branch_points.clone()
        self.terminals_copy = self.terminals.clone()

        # reset bundle density
        self.bundle_density = torch.zeros_like(self.true_density.data)
        self.bundle_density = Image(self.bundle_density)
        # self.img.data[3:] = torch.zeros((3,)+self.img.data.shape[1:]) # zero out path, bifurcation, and terminal point channels
        # self.img.data[3:] = torch.zeros((2,)+self.img.data.shape[1:]) # zero out path, and bifurcation point channels
        self.img.data[3:] = torch.zeros((1,)+self.img.data.shape[1:]) # zero out path #TODO: changed for testing
        for i in range(len(self.paths)):
            for j in range(len(self.paths[i])-1):
                segment = torch.stack((self.paths[i][j], self.paths[i][j+1]), dim=0)
                self.img.draw_line_segment(segment, width=0, channel=3)
                self.bundle_density.draw_line_segment(segment, width=self.step_width)

        return