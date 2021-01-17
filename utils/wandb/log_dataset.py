import argparse
import logging
import os
import random
import time
from pathlib import Path
from threading import Thread
from warnings import warn

import torch
import yaml
import wandb
from utils.wandb_utils import WandbLogger

from utils.general import check_dataset
from utils.torch_utils import torch_distributed_zero_first
from utils.datasets import create_dataloader

WANDB_ARTIFACT_PREFIX = 'wandb-artifact://'

def create_dataset_artifact(opt):
    with open(opt.data) as f:
        data_dict = yaml.load(f, Loader=yaml.FullLoader)  # data dict
    wandb_logger = WandbLogger(opt, '', None, data_dict, job_type='create_dataset')
    # Hyperparameters
    with open(opt.hyp) as f:
        hyp = yaml.load(f, Loader=yaml.FullLoader)  # load hyps

    with torch_distributed_zero_first(-1):
        check_dataset(data_dict)  # check
    train_path = data_dict['train']
    test_path = data_dict['val']
    nc, names = (1, ['item']) if opt.single_cls else (int(data_dict['nc']), data_dict['names'])
    imgsz, batch_size = opt.img_size, opt.batch_size
    assert len(names) == nc, '%g names found for nc=%g dataset in %s' % (len(names), nc, opt.data)  # check
    trainloader = create_dataloader(train_path, imgsz, batch_size, 32, opt,
                                            hyp=hyp, cache=opt.cache_images, rect=opt.rect, rank=-1,
                                            world_size=1, workers=opt.workers)[0]
    
    testloader = create_dataloader(test_path, imgsz, batch_size, 32, opt,  # testloader
                                       hyp=hyp, cache=opt.cache_images, rect=True,
                                       rank=-1, world_size=1, workers=opt.workers, pad=0.5)[0]
    names_to_ids = {k: v for k, v in enumerate(names)}

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    wandb_logger.log_dataset_artifact(trainloader, device, names_to_ids, name='train')
    wandb_logger.log_dataset_artifact(testloader, device, names_to_ids, name='val')
    #Update/Create new config file with links to artifact
    data_dict['train'] = WANDB_ARTIFACT_PREFIX + opt.project + '/train'
    data_dict['val'] = WANDB_ARTIFACT_PREFIX + opt.project + '/val'
    ouput_data_config = opt.data if opt.overwrite_config else opt.data.replace('.','_wandb.')
    data_dict.pop('download',None) #Don't download the original dataset. Use artifacts
    with open(ouput_data_config, 'w') as fp:
        yaml.dump(data_dict, fp)
    print("New Config file => ", ouput_data_config)
    
    
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=str, default='data/coco128.yaml', help='data.yaml path')
    parser.add_argument('--single-cls', action='store_true', help='train as single-class dataset')
    parser.add_argument('--image-weights', action='store_true', help='use weighted image selection for training')
    parser.add_argument('--rect', action='store_true', help='rectangular training')
    parser.add_argument('--cache-images', action='store_true', help='cache images for faster training')
    parser.add_argument('--workers', type=int, default=8, help='maximum number of dataloader workers')
    parser.add_argument('--project', type=str, default='yolov5', help='name of W&B Project')
    parser.add_argument('--img-size', nargs='+', type=int, default=640, help='[train, test] image sizes')
    parser.add_argument('--batch-size', type=int, default=16, help='total batch size for all GPUs')
    parser.add_argument('--hyp', type=str, default='data/hyp.scratch.yaml', help='hyperparameters path')
    parser.add_argument('--overwrite_config', action='store_true', help='replace the origin data config file')
    opt = parser.parse_args()

    create_dataset_artifact(opt)
        





    
    
