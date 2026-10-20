import {jsxDEV as original,Fragment} from 'react/jsx-dev-runtime';
import {translateProps} from './index.js';
export {Fragment};
export const jsxDEV=(type,props,...rest)=>original(type,translateProps(type,props),...rest);
