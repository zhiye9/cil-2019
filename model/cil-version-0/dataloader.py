import cv2
import torch
import numpy as np
from torch.utils import data

from config import config
from utils.img_utils import random_scale, random_mirror, normalize, \
    generate_random_crop_pos, random_crop_pad_to_shape

# assign a label to a patch
def patch_to_label(patch, foreground_threshold=0.25):
    # percentage of pixels > 1 required to assign a foreground label to a patch
    df = np.mean(patch)
    if df > foreground_threshold * 237:
        return np.ones_like(patch)
    else:
        return np.zeros_like(patch)

def img_binary(img, patch_size = 16, foreground_threshold=0.25):
    for j in range(0, img.shape[1], patch_size):
        for i in range(0, img.shape[0], patch_size):
            patch = img[i:i + patch_size, j:j + patch_size]
            img[i:i + patch_size, j:j + patch_size] = patch_to_label(patch)

    return img

def img_to_black(img):
    # change img to black
    img = img.astype(np.int64)
    idx = img[:,:] > 100
    idx_0 = img[:,:] <= 100
    img[idx] = 1
    img[idx_0] = 0
    return img

class TrainPre(object):
    """Binary labels to the groundtruth, mirrored, cropped randomly"""
    def __init__(self, img_mean, img_std):
        self.img_mean = img_mean
        self.img_std = img_std

    def __call__(self, img, gt):
        img, gt = random_mirror(img, gt)
        gt = img_binary(gt)

        if config.train_scale_array is not None:
            img, gt, scale = random_scale(img, gt, config.train_scale_array)

        img = normalize(img, self.img_mean, self.img_std)

        crop_size = (config.image_height, config.image_width)
        crop_pos = generate_random_crop_pos(img.shape[:2], crop_size)

        p_img, _ = random_crop_pad_to_shape(img, crop_pos, crop_size, 0)
        p_gt, _ = random_crop_pad_to_shape(gt, crop_pos, crop_size, 255)
        p_gt = cv2.resize(p_gt, (config.image_width // config.gt_down_sampling,
                                 config.image_height // config.gt_down_sampling),
                          interpolation=cv2.INTER_NEAREST)

        p_img = p_img.transpose(2, 0, 1)
        #p_gt = np.expand_dims(p_gt, axis=0)
        #p_gt = p_gt.astype(np.float)
        extra_dict = None

        return p_img, p_gt, extra_dict


def get_train_loader(engine, dataset):
    data_setting = {'img_root': config.img_root_folder,
                    'gt_root': config.gt_root_folder,
                    'train_source': config.train_source,
                    'eval_source': config.eval_source,
                    'test_source': config.test_source}
    train_preprocess = TrainPre(config.image_mean, config.image_std)

    train_dataset = dataset(data_setting, "train", train_preprocess,
                            config.batch_size * config.niters_per_epoch)

    train_sampler = None
    is_shuffle = True
    batch_size = config.batch_size

    train_loader = data.DataLoader(train_dataset,
                                   batch_size=batch_size,
                                   num_workers=config.num_workers,
                                   drop_last=True,
                                   shuffle=is_shuffle,
                                   pin_memory=True,
                                   sampler=train_sampler)

    return train_loader, train_sampler
