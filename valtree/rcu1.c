#include "fake_defs.h"
#include "fake_sync.h"
#include <linux/rcupdate.h>
#include <rcupdate.c>
#include "rcutree.c"
#include "fake_sched.h"

int cpu0 = 0;
int cpu1 = 1;


_Atomic int pub_finished;
_Atomic int pub_cur;
_Atomic int pub_seq;
_Atomic int pub_vote;
_Atomic int pub_prev;
_Atomic int pub_version;


int r_finished;
int r_cur;
int r_seq;
int r_vote;
int r_prev;
int r_version;

void *thread_reader(void *arg)
{
	set_cpu(cpu1);
	fake_acquire_cpu(get_cpu());

	rcu_read_lock();
	r_finished = atomic_load_explicit(&pub_finished, memory_order_acquire);
	do_IRQ();
	r_cur = atomic_load_explicit(&pub_cur, memory_order_acquire);
	r_seq = atomic_load_explicit(&pub_seq, memory_order_acquire);
	do_IRQ();
	r_vote = atomic_load_explicit(&pub_vote, memory_order_acquire);
	r_version = atomic_load_explicit(&pub_version, memory_order_acquire);
	do_IRQ();
	r_prev = atomic_load_explicit(&pub_prev, memory_order_acquire);
	rcu_read_unlock();

	cond_resched();
	do_IRQ();

	fake_release_cpu(get_cpu());
	return NULL;
}

void *thread_update(void *arg)
{
	set_cpu(cpu0);
	fake_acquire_cpu(get_cpu());

	atomic_store_explicit(&pub_cur, 0xbb, memory_order_release);
	atomic_store_explicit(&pub_seq, 24, memory_order_release);
	atomic_store_explicit(&pub_version, 1, memory_order_release);

#ifdef CHECK_BUG
	/* Bug: valid is published before dependent fields are complete. */
	atomic_store_explicit(&pub_finished, 1, memory_order_release);
	do_IRQ();
	cond_resched();
	do_IRQ();
	atomic_store_explicit(&pub_vote, 100, memory_order_release);
	do_IRQ();
	cond_resched();
	do_IRQ();
	atomic_store_explicit(&pub_prev, 0xaa, memory_order_release);
#else
	atomic_store_explicit(&pub_vote, 100, memory_order_release);
	atomic_store_explicit(&pub_prev, 0xaa, memory_order_release);
	atomic_store_explicit(&pub_finished, 1, memory_order_release);
#endif

	fake_release_cpu(get_cpu());
	return NULL;
}

void *thread_helper(void *arg)
{
	set_cpu(cpu0);
	fake_acquire_cpu(get_cpu());

	do_IRQ();
	cond_resched();
	do_IRQ();

	fake_release_cpu(get_cpu());
	return NULL;
}

int main(void)
{
	pthread_t tu, th;

	rcu_scheduler_fully_active = 1;
	rcu_init();
	for (int i = 0; i < NR_CPUS; i++) {
		set_cpu(i);
		rcu_enter_nohz();
	}

	atomic_store(&pub_finished, 0);
	atomic_store(&pub_cur, 0xbb);
	atomic_store(&pub_seq, 24);
	atomic_store(&pub_vote, 90);
	atomic_store(&pub_prev, 0x0a000001);
	atomic_store(&pub_version, 0);

	r_finished = 0;
	r_cur = 0;
	r_seq = 0;
	r_vote = 0;
	r_prev = 0;
	r_version = 0;

	if (pthread_create(&tu, NULL, thread_update, NULL))
		abort();
	if (pthread_create(&th, NULL, thread_helper, NULL))
		abort();
	(void)thread_reader(NULL);

	if (pthread_join(tu, NULL))
		abort();
	if (pthread_join(th, NULL))
		abort();

#ifdef CHECK_BUG
	if (r_finished == 1) {
		if (r_cur == 0xbb) {
			if (r_seq == 24) {
				if (r_vote == 100) {
					BUG_ON(r_prev != 0xaa);
				}
			}
		}
	}
#endif

	return 0;
}
