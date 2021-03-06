"""
@author: Matthias Grueter <matthias@grueter.name>
@copyright: Copyright (c) 2012 Matthias Grueter
@license: GPL

"""
import config
import Queue

from stage import Stage


#class PipelineState():
#    EMPTY = 0       # all stages and buffers are empty
#    ACTIVE  = 5     # one or more stages are active and one or more buffers are not empty
#    PAUSED = 4      # all stages are paused and one or more buffers are not empty
#    IDLE = 1        # all stages are paused and all buffers are empty
#    FINISHING = 2   # one or more stages are active and all buffers are empty
#    CLOGGED = 3     # one or more stage with non-empty buffer is unstaffed    



# TODO: unit tests
# TODO: implement some sort of dispatcher to dynamically create or kill threads
#       in each stage to optimize performance (e.g. workers are only started if
#       something is in its input queue, number of workers is adapted according
#       to workload and worker performance.)
class Pipeline():
    """
    Pipeline defines the stages of the workflow.
    """

    def __init__(self, name, recipe, path):
        self.name = name
        # recipe defining the sequence of jobs to be performed
        self.recipe = recipe
        self.num_stages = self.recipe.num_stages
        self.num_stageworkers = config.STAGE_SIZE
        # Create buffers before and after each stage (hand-off points)
        self.buffers = [Queue.Queue() for i in range(self.num_stages + 1)]
        # The input buffer of the pipeline.
        self.input = self.buffers[0]
        # The output buffer of the pipeline
        self.output = self.buffers[-1]
        # Stage environment variables
        self.stage_environ = dict(pipeline=self, path=path)
        # Create stages and connect them to the buffers
        self.stages = [Stage(name=self.recipe.stage_names[i],
                             WorkerClass=self.recipe.stage_types[i],
                             num_workers=self.num_stageworkers,
                             in_buffer=self.buffers[i],
                             out_buffer=self.buffers[i + 1],
                             seq_number=i,
                             **self.stage_environ) for i in range(self.num_stages)]
        # jobnr is a simple counter of jobs that have been or still are processed
        self.jobnr = 0
        # Set state to inactive
        # FIXME: isactive should be a descriptor and depend on stage's status
        self.isactive = False


    def put(self, picture):
        """Put a Job object into the pipeline"""
        # FIXME: make access to self.jobnr thread-safe (locking)
        self.jobnr += 1
        self.input.put((picture, self.jobnr))

    def get_progress(self):
        """Returns a list of the number of jobs in each queue"""
        return [b.qsize() for b in self.buffers]

    def start(self):
        """Start all workers"""
        self.isactive = True
        [s.start() for s in self.stages]

    def flush(self):
        """Flushes all queues"""
        # TODO: How to flush queues?
        raise(NotImplementedError('Queue flushing'))

    def stop(self):
        """
        Stops all workers.
        Blocks until all workers have completed their current job.
        """
        [s.stop() for s in self.stages]
        self.isactive = False

    def abort(self):
        """Immediately terminate all worker threads and flush queues"""
        # FIXME: Is it possible to kill threads?
#        raise(NotImplementedError('Aborting pipline'))
        print('Aborting is not implemented yet. Stopping instead and flushing queues.')
        self.stop()
        self.flush()

    def join(self):
        """
        Finish all pending jobs.
        Blocks until all stages' input queues are empty.
        """
        [s.join() for s in self.stages]
        self.isactive = False

    def get_total_progress(self):
        """
        Determine overall progress by checking size of output queue.
        """
        # TODO: is this accurate enough? it should be. Otherwise we could get
        #       all items from output queue and then count them and add them up.
        return self.output.qsize()


# Unit test       
def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()

