// Synthetic OpenProject webhook event generator. Mirrors event shapes
// from https://www.openproject.org/docs/api/webhooks/
// keep this small + cheap so vus don't bottleneck on cpu.

const ACTIONS = [
  'work_package:created',
  'work_package:updated',
  'project:created',
  'time_entry:created',
  'attachment:created',
];

const SUBJECTS = [
  'Investigate kafka lag',
  'Patch eks node group',
  'Rotate iam keys',
  'Wire prometheus servicemonitor',
  'Bench tool latency',
];

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function makeEvent() {
  const action = pick(ACTIONS);
  const id = Math.floor(Math.random() * 100000) + 1;
  return {
    action,
    event_at: new Date().toISOString(),
    resource: {
      id,
      _type: action.split(':')[0],
      subject: pick(SUBJECTS),
      project: { id: Math.floor(Math.random() * 50) + 1 },
    },
  };
}
